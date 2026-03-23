"""Interactive shell mode for Job Sniper using prompt_toolkit."""

import os
import shlex
import subprocess
import sys

HISTORY_PATH = os.path.join(os.path.expanduser("~"), ".job-sniper", "history")

COMMANDS = {
    "add":       "Add a company to the outreach queue",
    "process":   "Apollo lookup \u2192 verify \u2192 generate drafts",
    "drafts":    "List ready drafts (or: drafts show #)",
    "update":    "Update a company's outreach status",
    "followups": "Show overdue follow-ups with drafts",
    "status":    "Dashboard with stats and API credits",
    "help":      "Show this help message",
    "exit":      "Exit the shell",
}

COMMAND_FLAGS = {
    "add":     ["--company", "-c", "--role", "-r", "--url", "-u", "--notes", "-n", "--applied", "-a"],
    "process": ["--dry-run"],
    "update":  ["--status", "-s"],
    "drafts":  ["show"],
}

STATUS_VALUES = ["emailed", "followed_up", "replied", "interview", "dead", "stale"]


def _build_completer():
    from prompt_toolkit.completion import Completer, Completion

    class SniperCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            try:
                parts = shlex.split(text)
            except ValueError:
                parts = text.split()

            completing_new = text.endswith(" ")

            if not parts or (len(parts) == 1 and not completing_new):
                word = parts[0] if parts else ""
                for cmd in list(COMMANDS) + ["quit"]:
                    if cmd.startswith(word):
                        yield Completion(cmd, start_position=-len(word))
                return

            cmd = parts[0]

            # --status value completion for update
            if cmd == "update":
                token_before = parts[-1] if completing_new else (parts[-2] if len(parts) >= 2 else "")
                if token_before in ("--status", "-s"):
                    word = "" if completing_new else parts[-1]
                    for val in STATUS_VALUES:
                        if val.startswith(word):
                            yield Completion(val, start_position=-len(word))
                    return

            # "drafts show" subcommand
            if cmd == "drafts" and (len(parts) == 1 and completing_new or len(parts) == 2 and not completing_new):
                word = parts[1] if len(parts) == 2 and not completing_new else ""
                if "show".startswith(word):
                    yield Completion("show", start_position=-len(word))
                return

            # Flag completion
            if cmd in COMMAND_FLAGS:
                word = "" if completing_new else parts[-1]
                for flag in COMMAND_FLAGS[cmd]:
                    if flag.startswith(word) and flag not in parts:
                        yield Completion(flag, start_position=-len(word))

    return SniperCompleter()


def _print_help():
    print("\nAvailable commands:\n")
    for cmd, desc in COMMANDS.items():
        print(f"  {cmd:<12} {desc}")
    print()


def _make_prompt_func():
    """Try to build a prompt_toolkit prompt function. Returns plain input() fallback on failure."""
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
        from prompt_toolkit.formatted_text import HTML
        from prompt_toolkit.history import FileHistory

        session = PromptSession(
            history=FileHistory(HISTORY_PATH),
            auto_suggest=AutoSuggestFromHistory(),
            completer=_build_completer(),
        )

        def prompt():
            return session.prompt(HTML("<ansigreen>sniper&gt; </ansigreen>"))

        return prompt
    except Exception:
        def prompt():
            return input("sniper> ")

        return prompt


def run_shell():
    """Launch the interactive sniper> REPL."""
    from . import db
    db.init_db()

    prompt = _make_prompt_func()

    print("Job Sniper interactive shell. Type 'help' for commands, 'exit' to quit.\n")

    while True:
        try:
            line = prompt()
        except KeyboardInterrupt:
            print()
            continue
        except EOFError:
            print("exit")
            break

        line = line.strip()
        if not line:
            continue

        try:
            args = shlex.split(line)
        except ValueError as e:
            print(f"Parse error: {e}")
            continue

        cmd = args[0]

        if cmd in ("exit", "quit"):
            break
        if cmd == "help":
            _print_help()
            continue
        if cmd not in COMMANDS:
            print("Unknown command. Type 'help' for available commands.")
            continue

        subprocess.run([sys.executable, "-m", "job_sniper"] + args)
