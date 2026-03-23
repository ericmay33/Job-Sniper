# Job Sniper — Architecture Document (Updated March 22, 2026)

## Build Status

| # | Module | File | Status |
|---|--------|------|--------|
| 1 | Project scaffold + SQLite | config.py, db.py, requirements.txt, .env.example | ✅ DONE |
| 2 | CLI skeleton (Typer) | sniper.py | ✅ DONE |
| 3 | Apollo API integration | apollo.py | ✅ DONE |
| 4 | Verification fallback chain | verify.py | ✅ DONE |
| 5 | Email templates (editable JSON) | templates.py, templates.json | ✅ DONE |
| 6 | Rich display module | display.py | ❌ NOT STARTED |
| 7 | Polish + integration test | all files | ❌ NOT STARTED |

**What works right now:** The full pipeline runs end-to-end — `add` → `process` (Apollo → Hunter/ZeroBounce → generate draft → status=ready) → `drafts` → `drafts show` → `update` → `followups` → `status`. All Rich output is currently inline in sniper.py (not in a separate display.py). Templates are editable via templates.json.

**What remains:** Prompt 6 extracts display logic into display.py for cleaner separation. Prompt 7 is a full integration test + polish pass.

---

## Overview

A local Python CLI tool that automates cold email outreach to recruiters and engineering managers. Discovers contacts via Apollo API, verifies emails via Hunter/ZeroBounce rotating fallback, generates personalized drafts from editable JSON templates, tracks everything in SQLite, displays it via Rich terminal tables.

**Hard constraints:** No web server, no OAuth, no Jinja2, no frontend. One directory, a few Python files, one SQLite database file. Runs entirely in the terminal.

---

## Current File Structure

```
job-sniper/
├── sniper.py          # CLI entry point (Typer app, all commands + inline Rich display)
├── db.py              # SQLite schema init + 14 helper functions
├── apollo.py          # Apollo API integration (contact discovery)
├── verify.py          # Hunter + ZeroBounce verification fallback chain
├── templates.py       # Loads templates.json, generates drafts + follow-ups
├── config.py          # API keys from env vars (.env via dotenv), constants
├── requirements.txt   # typer[all], rich, requests, pyperclip, python-dotenv
├── .env.example       # Template for API keys
├── templates.json     # Auto-generated on first run, user-editable email templates
└── sniper.db          # SQLite database (auto-created on first run)
```

**Not yet created:** display.py (Prompt 6 will extract Rich display functions from sniper.py)

---

## 1. config.py — Configuration (BUILT)

- Loads .env via `python-dotenv` at import time
- Exposes: APOLLO_API_KEY, HUNTER_API_KEY, ZEROBOUNCE_API_KEY
- DB_PATH: sniper.db in same directory
- Credit limits: HUNTER_MONTHLY_LIMIT=25, ZEROBOUNCE_MONTHLY_LIMIT=100
- Follow-up timing: FOLLOWUP_1_DAYS=4, FOLLOWUP_2_DAYS=10, FOLLOWUP_3_DAYS=7

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

### 14 Helper Functions (all implemented)

- init_db() — idempotent schema creation
- add_company() — with explicit duplicate company detection (handles NULL contact_email case)
- get_queued(), get_ready(), get_by_status() — query helpers
- update_company() — arbitrary field updates with auto updated_at
- update_status() — status transitions with special handling for emailed (sets date) and followed_up (increments count + logs followup_N)
- get_followups_due() — timing-based follow-up logic with auto-dead after 3 follow-ups
- get_status_counts(), get_credit_usage(), increment_credits() — dashboard/credit helpers using UPSERT
- get_company_by_id(), search_company() — lookup helpers

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

- **templates.json** auto-generates with defaults on first run (json.dump with indent=4)
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

## 6. display.py — Rich Terminal Output (NOT YET BUILT)

This is the next step. Currently all Rich display logic lives inline in sniper.py. Prompt 6 should extract it into a dedicated display.py module.

### Functions to Extract/Implement

```python
def show_drafts_table(drafts: list[dict]) -> None:
    """Table: #, Company, Contact, Verified, Draft Preview.
    Verification color coding: green for verified, yellow for unverified, dim for None."""

def show_draft_detail(company: dict) -> None:
    """Rich Panel: header (company + contact + title), LinkedIn URL, email + verification,
    template type (A/B), full subject + body, reminder box (LinkedIn check, Gmail hover for unverified)."""

def show_followups_table(followups: list[dict]) -> None:
    """Table: Company, Contact, Days Since, Follow-up #, Draft Preview (60 chars)."""

def show_status_dashboard(counts: dict, credits: dict) -> None:
    """Panel dashboard: status counts, total, reply rate, API credits remaining."""

def show_process_preview(queued: list[dict]) -> None:
    """Dry-run table: #, Company, Role, Contact, Email, Verified (all "pending")."""
```

### Current State in sniper.py

The drafts table, drafts show panel, followups table, status dashboard, and process preview are all built and working — they're just inline in sniper.py command functions rather than in a separate display.py. Prompt 6 should refactor them out for cleaner code organization.

---

## 7. sniper.py — CLI Entry Point (BUILT)

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

- Windows UTF-8 fix applied: stdout/stderr reconfigured to UTF-8, Console(force_terminal=True)
- drafts is a Typer sub-group with callback(invoke_without_command=True) for listing + `show` subcommand
- Valid statuses: queued, ready, emailed, followed_up, replied, interview, dead, stale
- Entry point: `if __name__ == "__main__": app()`

---

## 8. Key Implementation Details

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

---

## 9. Remaining Build Prompts

### Prompt 6: Rich display extraction
```
Extract all Rich display logic from sniper.py into a new display.py module. Create these functions:
show_drafts_table(), show_draft_detail(), show_followups_table(), show_status_dashboard(), show_process_preview().
Update sniper.py to import and call display functions instead of inline Rich code.
Also review and improve the visual output:
- Make sure the drafts show panel matches the plan doc layout exactly (the ═══ header with company/contact/LinkedIn/email/template line, then the full email, then the reminder box at the bottom)
- Add color coding consistency: green for verified/success, yellow for unverified/warnings, red for errors, blue for info
- Make the status dashboard match the plan doc's box-drawing layout as closely as Rich allows
Test all commands still work after the refactor.
```

### Prompt 7: Polish + full integration test
```
Full integration test and polish pass:
1. Clean the DB, add 3-4 test companies (mix of --applied and proactive), run process --dry-run, run process (will fail gracefully without API keys), manually insert simulated contact data for testing, run drafts, drafts show 1, update to emailed, check followups, check status dashboard.
2. Fix any display bugs, alignment issues, or edge cases found during testing.
3. Make sure sniper --help is clean and all subcommand help text is descriptive.
4. Add a shebang line to sniper.py if not already present.
5. Verify templates.json auto-creates cleanly on fresh run.
6. Test edge cases: empty database, update nonexistent company, drafts show with invalid index, followups when none due.
```

---

## 10. What Success Looks Like

After the build, these commands all work:

```bash
# Queue companies
sniper add --company "Cloudflare" --role "New Grad SWE" --url "https://..." --applied
sniper add --company "Tailscale" --role "DevOps / Infra" --notes "Love their WireGuard approach"

# Batch process
sniper process --dry-run     # preview, no API calls
sniper process               # Apollo + verify + generate drafts

# View and send
sniper drafts                # table of ready drafts
sniper drafts show 1         # full draft + LinkedIn + clipboard copy

# Track
sniper update cloudflare --status emailed
sniper update cloudflare --status replied

# Follow up
sniper followups             # overdue follow-ups with auto-generated drafts

# Dashboard
sniper status                # counts, reply rate, API credits
```

Every command has clean Rich output. Every error has a human-readable message. The database is one file. Templates are editable via JSON.
