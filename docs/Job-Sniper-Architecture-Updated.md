# Job Sniper — Architecture Document (Updated March 23, 2026)

## Build Status

| # | Module | File | Status |
|---|--------|------|--------|
| 1 | Project scaffold + SQLite | config.py, db.py, requirements.txt, .env.example | ✅ DONE |
| 2 | CLI skeleton (Typer) | cli.py | ✅ DONE |
| 3 | Apollo API integration | apollo.py | ✅ DONE |
| 4 | Verification fallback chain | verify.py | ✅ DONE |
| 5 | Email templates (editable JSON) | templates.py, ~templates.json~ | ✅ DONE |
| 6 | Rich display module | display.py | ✅ DONE |
| 7 | Polish + integration test | all files | ✅ DONE |
| 8 | Interactive shell (prompt_toolkit) | shell.py | ✅ DONE |
| 9 | Installable package restructure | pyproject.toml, __init__.py, __main__.py | ✅ DONE |

**What works right now:** The full pipeline runs end-to-end — `add` → `process` (Apollo → Hunter/ZeroBounce → generate draft → status=ready) → `drafts` → `drafts show` → `update` → `followups` → `status`. Rich display logic extracted into display.py. Templates are editable via ~/.job-sniper/templates.json. Interactive shell with tab completion, command history, and colored prompt. Installable as a package via `pip install -e .` with a `sniper` console entry point. All commands tested end-to-end with edge case coverage.

---

## Overview

A local Python CLI tool that automates cold email outreach to recruiters and engineering managers. Discovers contacts via Apollo API, verifies emails via Hunter/ZeroBounce rotating fallback, generates personalized drafts from editable JSON templates, tracks everything in SQLite, displays it via Rich terminal tables.

**Hard constraints:** No web server, no OAuth, no Jinja2, no frontend. Installable Python package in `src/job_sniper/`. One SQLite database file at `~/.job-sniper/sniper.db`. Runs entirely in the terminal.

---

## Current File Structure

```
Job-Sniper/
├── pyproject.toml                  # Package config, setuptools, sniper entry point
├── .env.example                    # API key template
├── README.md
├── CLAUDE.md
├── docs/
│   └── Job-Sniper-Architecture-Updated.md
└── src/
    ├── requirements.txt            # Legacy deps list (canonical source: pyproject.toml)
    └── job_sniper/
        ├── __init__.py             # __version__ = "1.0.0"
        ├── __main__.py             # python -m job_sniper support
        ├── cli.py                  # Typer CLI app + main() entry point
        ├── shell.py                # Interactive REPL (prompt_toolkit)
        ├── display.py              # Rich display functions (tables, panels, dashboard)
        ├── db.py                   # SQLite schema init + 12 helper functions
        ├── apollo.py               # Apollo API integration (contact discovery)
        ├── verify.py               # Hunter + ZeroBounce verification fallback chain
        ├── templates.py            # Loads ~/.job-sniper/templates.json, generates drafts + follow-ups
        └── config.py               # API keys, constants, data dir, Windows UTF-8 fix

~/.job-sniper/                      # User data directory (auto-created)
├── sniper.db                       # SQLite database
├── templates.json                  # Auto-generated on first use, user-editable
├── .env                            # API keys (user-created)
└── history                         # Shell command history
```

---

## 1. config.py — Configuration (BUILT)

- DATA_DIR: `~/.job-sniper/` (created automatically via `os.makedirs`)
- Loads .env via `python-dotenv` at import time — checks `~/.job-sniper/.env` first, then cwd `.env` as fallback
- Exposes: APOLLO_API_KEY, HUNTER_API_KEY, ZEROBOUNCE_API_KEY
- DB_PATH: `~/.job-sniper/sniper.db`
- Credit limits: HUNTER_MONTHLY_LIMIT=25, ZEROBOUNCE_MONTHLY_LIMIT=100
- Follow-up timing: FOLLOWUP_1_DAYS=4, FOLLOWUP_2_DAYS=10, FOLLOWUP_3_DAYS=7
- **Windows UTF-8 fix:** Reconfigures stdout/stderr to UTF-8 on Windows. Consolidated here because every module imports config directly or transitively.

---

## 2. db.py — SQLite Schema + Helpers (BUILT)

### Schema (3 tables)

```sql
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    role TEXT,
    url TEXT,
    notes TEXT,
    applied INTEGER DEFAULT 0,
    status TEXT DEFAULT 'queued',
    contact_name TEXT,
    contact_title TEXT,
    contact_email TEXT,
    contact_linkedin TEXT,
    verification_status TEXT,
    draft_body TEXT,
    draft_subject TEXT,
    emailed_date TEXT,
    followup_count INTEGER DEFAULT 0,
    last_followup_date TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(company, contact_email)
);

CREATE TABLE IF NOT EXISTS api_credits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    month TEXT NOT NULL,
    credits_used INTEGER DEFAULT 0,
    UNIQUE(service, month)
);

CREATE TABLE IF NOT EXISTS outreach_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);
```

### 12 Helper Functions

- init_db() — idempotent schema creation
- add_company() — with explicit duplicate company detection (handles NULL contact_email case)
- get_queued(), get_ready(), get_by_status() — query helpers
- update_company() — arbitrary field updates with auto updated_at
- update_status() — status transitions with special handling for emailed (sets date) and followed_up (increments count + logs followup_N)
- get_followups_due() — timing-based follow-up logic with auto-dead after 3 follow-ups
- get_status_counts(), get_credit_usage(), increment_credits() — dashboard/credit helpers using UPSERT
- search_company() — case-insensitive partial match lookup

---

## 3. apollo.py — Contact Discovery (BUILT)

- POST to `https://api.apollo.io/api/v1/mixed_people/search`
- Searches for recruiter/hiring manager titles at given company
- Sorts results: recruiter-type titles first, then eng manager titles
- Returns first match with a non-empty email: {name, first_name, title, email, linkedin_url}
- Returns None if no results or no one has email
- Tracks credits via db.increment_credits("apollo")
- Error handling: missing key, request exceptions, non-200 status — all return None gracefully

---

## 4. verify.py — Verification Fallback Chain (BUILT)

- verify_email(email) → "verified_hunter" | "verified_zerobounce" | "unverified"
- _try_hunter(): checks monthly credit limit (25), GET Hunter email-verifier, accepts "valid"/"accept_all"
- _try_zerobounce(): checks monthly credit limit (100), GET ZeroBounce validate, accepts "valid"/"catch-all"
- Skips service silently if API key missing, falls through on errors
- Credits tracked after every API call
- Never crashes — always returns one of three valid strings

---

## 5. templates.py — Editable Email Templates (BUILT)

- **~/.job-sniper/templates.json** auto-generates with defaults on first use (json.dump with indent=4)
- User edits templates.json directly to customize wording — no Python changes needed
- generate_draft(company, role, first_name, contact_title, applied, url, notes) → (subject, body)
  - applied=True → templates["applied"] (Template A)
  - applied=False → templates["proactive"] (Template B)
  - Uses .format() with {first_name}, {role}, {company}
- generate_followup(company, first_name, original_subject, followup_number) → (subject, body)
  - Subject: "Re: {original_subject}"
  - Body from templates["followups"][str(followup_number)]
- Error handling: invalid JSON prints fix-or-delete message and exits; missing keys caught

### Default Template Content

**Template A (applied):**
- Subject: `Quinnipiac CS Senior — {role} Application`
- Body: Intro → Merck internship → AI DevOps agent → [WHY THEM placeholder] → CTA → sign-off

**Template B (proactive):**
- Subject: `CS New Grad | Merck SWE Intern + AWS Certified — {company} Interest`
- Body: Intro → Merck internship → AI DevOps agent → [WHY THEM placeholder] → CTA → sign-off

**Follow-ups 1-3:** Short, progressively softer, final one closes the loop.

---

## 6. display.py — Rich Terminal Output (BUILT)

All Rich display logic extracted from cli.py into display.py.

### Functions

- `show_drafts_table(drafts)` — Table: #, Company, Contact, Verified, Draft Preview
- `show_draft_detail(c, number)` — Panel: ═══ header, contact info, LinkedIn, email + verification, template type, subject + body, reminder box
- `show_followups_table(followups)` — Table: Company, Contact, Days Since, Follow-up #, Draft Preview
- `show_status_dashboard(counts, credits)` — Panel dashboard: color-coded status counts, reply rate, API credits
- `show_process_preview(queued)` — Dry-run table: all fields "pending"

### Color Coding

- Green: verified (hunter/zerobounce), replied, interview
- Yellow: unverified, emailed, followed_up
- Red: dead, stale
- Blue: queued, info headers
- Cyan: ready

---

## 7. cli.py — CLI Entry Point (BUILT)

### Current Command Status

| Command | Status | Notes |
|---------|--------|-------|
| `sniper add` | ✅ Working | --company, --role, --url, --notes, --applied flags. Duplicate prevention. |
| `sniper process` | ✅ Working | Full pipeline: Apollo → verify → generate draft → save → status=ready. Dry-run shows queue without API calls. |
| `sniper process --dry-run` | ✅ Working | Shows queued companies table, no API credits burned. |
| `sniper drafts` | ✅ Working | Rich table of all ready drafts with verification status + preview. |
| `sniper drafts show [#]` | ✅ Working | Full panel with LinkedIn URL, verification, template type, clipboard copy. |
| `sniper followups` | ✅ Working | Shows overdue follow-ups with auto-generated draft previews. |
| `sniper status` | ✅ Working | Dashboard: counts by status, reply rate, API credits remaining. |
| `sniper update` | ✅ Working | Partial match company name, validates status, special handling for emailed/followed_up. |

### Implementation Notes

- Windows UTF-8 fix consolidated in config.py (imported transitively by all modules)
- drafts is a Typer sub-group with callback(invoke_without_command=True) for listing + `show` subcommand
- Valid statuses: queued, ready, emailed, followed_up, replied, interview, dead, stale
- `main()` function dispatches based on arguments: no args → interactive shell (shell.py), otherwise → Typer CLI
- Entry point registered in pyproject.toml: `sniper = "job_sniper.cli:main"`
- Also runnable via `python -m job_sniper` (__main__.py)

---

## 8. shell.py — Interactive Shell (BUILT)

Interactive REPL mode launched when `sniper` is run with no arguments.

### Features

- **prompt_toolkit integration:** PromptSession with colored `sniper>` prompt, FileHistory for persistent command history, AutoSuggestFromHistory for inline suggestions
- **Tab completion:** Custom SniperCompleter with context-aware completion:
  - Command names (add, process, drafts, update, followups, status, help, exit)
  - Flags per command (e.g. `add --company`, `process --dry-run`)
  - Status values after `--status`/`-s` flag (emailed, followed_up, replied, etc.)
  - `drafts show` subcommand
- **Graceful fallback:** If prompt_toolkit fails to initialize (piped stdin, non-TTY, mintty), falls back to plain `input()` prompt
- **Command dispatch:** Commands forwarded via `subprocess.run([sys.executable, "-m", "job_sniper"] + args)` — works regardless of install location
- **History file:** `~/.job-sniper/history` (persistent across sessions)
- **Built-in commands:** `help` (shows command list), `exit`/`quit` (exits shell)
- **Error handling:** KeyboardInterrupt re-prompts, EOFError exits cleanly, unknown commands show help hint

---

## 9. Key Implementation Details

### Duplicate Prevention
Explicit company name check in add_company() (not relying on UNIQUE constraint since contact_email is NULL at queue time).

### Date Handling
ISO format via datetime.now().isoformat(). Days-since uses (datetime.now() - datetime.fromisoformat(date_str)).days.

### Clipboard
pyperclip.copy() wrapped in try/except — fails silently in headless environments.

### Credit Tracking
Monthly reset via YYYY-MM month column in api_credits table. UPSERT pattern for increment_credits.

### Auto-Dead After 3 Follow-ups
get_followups_due() auto-marks companies with followup_count >= 3 as "dead".

### Windows UTF-8 Fix
Consolidated in config.py — reconfigures sys.stdout and sys.stderr to UTF-8 with errors="replace". Runs once at import time since every module imports config directly or transitively via relative imports. Modules that don't naturally import config (like templates.py) use `from . import config  # noqa: F401` for the side effect.

### Package Structure
Installable Python package via `pip install -e .`. Entry point `sniper` registered in pyproject.toml. All internal imports use relative imports (`from . import db`). User data stored in `~/.job-sniper/` (DB, templates, .env, history) — not in the package directory.

---

## 10. Potential v1.1 Improvements

- **Reprocess command:** `sniper reprocess <company>` to re-run Apollo/verify for a specific company
- **Export to CSV:** `sniper export` to dump the pipeline to a spreadsheet for sharing
- **Email pattern guessing fallback:** When Apollo returns no email, guess firstname.lastname@company.com
- **Batch follow-up status updates:** `sniper update --all-emailed` to bulk-update after a send session
- **Terminal color theming:** Let users pick color schemes via config or environment variable
- **Shell improvements:** Multi-line input, company name completion from database, `!!` to repeat last command

---

## 11. What Success Looks Like

After `pip install -e .`, these commands all work from anywhere:

```bash
# Interactive mode
sniper                        # launches sniper> shell with tab completion

# Direct CLI mode
sniper add --company "Cloudflare" --role "New Grad SWE" --url "https://..." --applied
sniper add --company "Tailscale" --role "DevOps / Infra" --notes "Love their WireGuard approach"

# Batch process
sniper process --dry-run      # preview, no API calls
sniper process                # Apollo + verify + generate drafts

# View and send
sniper drafts                 # table of ready drafts
sniper drafts show 1          # full draft + LinkedIn + clipboard copy

# Track
sniper update cloudflare --status emailed
sniper update cloudflare --status replied

# Follow up
sniper followups              # overdue follow-ups with auto-generated drafts

# Dashboard
sniper status                 # counts, reply rate, API credits

# Alternative invocation
python -m job_sniper --help
```

Every command has clean Rich output. Every error has a human-readable message. The database lives at `~/.job-sniper/sniper.db`. Templates are editable via `~/.job-sniper/templates.json`. The interactive shell provides tab completion and command history.
