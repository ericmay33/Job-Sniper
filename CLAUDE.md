# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Job Sniper is a Python CLI tool that automates cold email outreach to recruiters and engineering managers for a new grad job search. It discovers contacts via Apollo API, verifies emails via Hunter/ZeroBounce rotating fallback, generates personalized email drafts from editable templates, tracks everything in SQLite, and displays output via Rich terminal tables.

**Hard constraints:** No web server, no OAuth, no Jinja2, no frontend. Source lives in `src/`, one SQLite database file. Runs entirely in the terminal.

## Architecture

The full build specification lives in `docs/Job-Sniper-Architecture-Updated.md`. Key design decisions:

- **Entry point:** `src/sniper.py` — Typer CLI app with commands: `add`, `process`, `drafts`, `drafts show`, `followups`, `status`, `update`
- **Data layer:** `src/db.py` — SQLite with 3 tables (`companies`, `api_credits`, `outreach_log`). Uses `sqlite3.Row` factory. All writes in transactions. `init_db()` called on every CLI invocation via Typer callback.
- **API integrations:** `src/apollo.py` (contact discovery via POST mixed_people/search), `src/verify.py` (Hunter → ZeroBounce fallback chain with monthly credit tracking)
- **Templates:** `src/templates.py` — reads from auto-generated `templates.json` (user-editable). Template A (applied/Funnel A) vs Template B (proactive/Funnel B). `[YOUR WHY THEM LINE]` placeholder stays literal for manual user editing.
- **Config:** `src/config.py` — API keys from env vars via `python-dotenv`. Constants for credit limits and follow-up timing.

## Commands

```bash
cd src
pip install -r requirements.txt          # Install dependencies
python sniper.py --help                  # Show all commands
python sniper.py add -c "Company" -r "Role" --applied   # Queue a company
python sniper.py process --dry-run       # Preview without API calls
python sniper.py process                 # Apollo lookup → verify → generate drafts
python sniper.py drafts                  # List ready drafts
python sniper.py drafts show 1           # Full draft detail + clipboard copy
python sniper.py update "Company" -s emailed   # Update status
python sniper.py followups               # Show overdue follow-ups
python sniper.py status                  # Dashboard with stats + API credits
```

## Key Design Patterns

- **Status machine:** `queued` → `ready` → `emailed` → `followed_up` → `replied`/`interview`/`dead`/`stale`. Tool sets `queued` and `ready` automatically; user sets the rest via `update`.
- **Verification fallback chain:** Hunter first (25/month free), then ZeroBounce (100/month free), then "unverified". Credits tracked per month in `api_credits` table (YYYY-MM key).
- **Follow-up cadence:** Follow-up 1 at +4 days, Follow-up 2 at +10 days after FU1, Follow-up 3 (final) at +7 days after FU2. Auto-mark "dead" after 3 follow-ups with no reply.
- **Duplicate prevention:** UNIQUE constraint on `(company, contact_email)` plus explicit check in `add_company`. Handle `sqlite3.IntegrityError` gracefully.
- **Clipboard:** `pyperclip` wrapped in try/except — fails silently in headless environments.
- **Windows compatibility:** UTF-8 output forced via `PYTHONUTF8` env var and stream reconfiguration in `sniper.py`.

## Environment Setup

Copy `src/.env.example` to `src/.env` and fill in API keys:
```
APOLLO_API_KEY=...
HUNTER_API_KEY=...
ZEROBOUNCE_API_KEY=...
```
