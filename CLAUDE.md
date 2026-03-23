# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Job Sniper is a Python CLI tool that automates cold email outreach to recruiters and engineering managers for a new grad job search. It discovers contacts via Apollo API, verifies emails via Hunter/ZeroBounce rotating fallback, generates personalized email drafts from editable templates, tracks everything in SQLite, and displays output via Rich terminal tables.

**Hard constraints:** No web server, no OAuth, no Jinja2, no frontend. Source lives in `src/job_sniper/` (installable package). One SQLite database file at `~/.job-sniper/sniper.db`. Runs entirely in the terminal.

## Architecture

The full build specification lives in `docs/Job-Sniper-Architecture-Updated.md`. Key design decisions:

- **Package:** `src/job_sniper/` — installable via `pip install -e .`, entry point `sniper` command
- **Entry point:** `src/job_sniper/cli.py` — Typer CLI app with commands: `add`, `process`, `drafts`, `drafts show`, `followups`, `status`, `update`. `main()` dispatches to shell (no args) or Typer (with args).
- **Data layer:** `src/job_sniper/db.py` — SQLite with 3 tables (`companies`, `api_credits`, `outreach_log`). Uses `sqlite3.Row` factory. All writes in transactions. `init_db()` called on every CLI invocation via Typer callback.
- **API integrations:** `src/job_sniper/apollo.py` (contact discovery via POST mixed_people/search), `src/job_sniper/verify.py` (Hunter → ZeroBounce fallback chain with monthly credit tracking)
- **Templates:** `src/job_sniper/templates.py` — reads from auto-generated `~/.job-sniper/templates.json` (user-editable). Template A (applied/Funnel A) vs Template B (proactive/Funnel B). `[YOUR WHY THEM LINE]` placeholder stays literal for manual user editing.
- **Config:** `src/job_sniper/config.py` — API keys from env vars via `python-dotenv` (checks `~/.job-sniper/.env` then cwd). Constants for credit limits and follow-up timing. Data directory: `~/.job-sniper/`.
- **Shell:** `src/job_sniper/shell.py` — interactive REPL, dispatches subcommands via `python -m job_sniper`.

## Commands

```bash
pip install -e .                         # Install as package
sniper --help                            # Show all commands
sniper                                   # Interactive shell mode
sniper add -c "Company" -r "Role" --applied   # Queue a company
sniper process --dry-run                 # Preview without API calls
sniper process                           # Apollo lookup → verify → generate drafts
sniper drafts                            # List ready drafts
sniper drafts show 1                     # Full draft detail + clipboard copy
sniper update "Company" -s emailed       # Update status
sniper followups                         # Show overdue follow-ups
sniper status                            # Dashboard with stats + API credits
python -m job_sniper --help              # Alternative invocation
```

## Key Design Patterns

- **Status machine:** `queued` → `ready` → `emailed` → `followed_up` → `replied`/`interview`/`dead`/`stale`. Tool sets `queued` and `ready` automatically; user sets the rest via `update`.
- **Verification fallback chain:** Hunter first (25/month free), then ZeroBounce (100/month free), then "unverified". Credits tracked per month in `api_credits` table (YYYY-MM key).
- **Follow-up cadence:** Follow-up 1 at +4 days, Follow-up 2 at +10 days after FU1, Follow-up 3 (final) at +7 days after FU2. Auto-mark "dead" after 3 follow-ups with no reply.
- **Duplicate prevention:** UNIQUE constraint on `(company, contact_email)` plus explicit check in `add_company`. Handle `sqlite3.IntegrityError` gracefully.
- **Clipboard:** `pyperclip` wrapped in try/except — fails silently in headless environments.
- **Windows compatibility:** UTF-8 output forced via stream reconfiguration in `config.py`.

## Environment Setup

Copy `.env.example` to `~/.job-sniper/.env` and fill in API keys:
```bash
mkdir -p ~/.job-sniper
cp .env.example ~/.job-sniper/.env
# edit ~/.job-sniper/.env with your real keys
```

The tool also checks for `.env` in the current working directory as a fallback.
