# Job Sniper

Cold email outreach automation for new grad job search. Discovers contacts via Apollo, verifies emails, generates personalized drafts, tracks everything in SQLite.

## Quick Start

```bash
pip install -e .
cp .env.example ~/.job-sniper/.env      # Add your API keys
sniper                                  # Launch interactive shell
```

## Usage

### Interactive Shell

Run with no arguments to enter the `sniper>` REPL with tab completion and command history:

```
$ sniper
Job Sniper interactive shell. Type 'help' for commands, 'exit' to quit.

sniper> add --company "Cloudflare" --role "New Grad SWE" --applied
✓ Queued: Cloudflare (New Grad SWE) (Funnel A — applied)

sniper> process --dry-run
sniper> status
```

### Direct CLI

Pass commands directly for scripting or one-off use:

```bash
sniper add --company "Cloudflare" --role "New Grad SWE" --applied
sniper process
sniper drafts show 1
```

You can also invoke via `python -m job_sniper`.

## Command Reference

| Command | Description |
|---------|-------------|
| `add -c <company> [-r role] [-u url] [-n notes] [-a]` | Queue a company. `-a` = already applied. |
| `process [--dry-run]` | Apollo lookup → verify email → generate draft. |
| `drafts` | List all ready-to-send drafts. |
| `drafts show <#>` | Full draft detail + copy to clipboard. |
| `update <company> -s <status>` | Update status: emailed, followed_up, replied, interview, dead, stale. |
| `followups` | Show overdue follow-ups with auto-generated drafts. |
| `status` | Dashboard: pipeline counts, reply rate, API credits. |

## Pipeline

```
add (queued) → process (ready) → update emailed → followups → replied/interview/dead
```

- **Funnel A:** Applied to a posting, emailing to follow up
- **Funnel B:** Proactive outreach, no application yet

## Templates

Email templates live in `~/.job-sniper/templates.json` (auto-generated on first use). Edit directly to customize wording — the `[YOUR WHY THEM LINE]` placeholder is left for you to fill in per company before sending.

## API Keys

Create `~/.job-sniper/.env` with:

```
APOLLO_API_KEY=...                # Contact discovery (10k credits/month)
HUNTER_API_KEY=...                # Email verification (25/month free)
ZEROBOUNCE_API_KEY=...            # Verification fallback (100/month free)
```

The tool also checks for `.env` in the current working directory as a fallback.

The tool works without keys — API calls fail gracefully and you can insert contact data manually.

## Data Storage

All user data lives in `~/.job-sniper/`:

| File | Description |
|------|-------------|
| `sniper.db` | SQLite database (auto-created on first run) |
| `templates.json` | Email templates (auto-generated, user-editable) |
| `.env` | API keys |
| `history` | Shell command history |

## Project Structure

```
Job-Sniper/
├── pyproject.toml                  # Package config + sniper entry point
├── .env.example                    # API key template
├── README.md
├── CLAUDE.md
├── docs/
│   └── Job-Sniper-Architecture-Updated.md
└── src/
    └── job_sniper/
        ├── __init__.py             # Package version
        ├── __main__.py             # python -m job_sniper support
        ├── cli.py                  # Typer CLI app + main() entry point
        ├── shell.py                # Interactive REPL (prompt_toolkit)
        ├── display.py              # Rich terminal output (tables, panels)
        ├── db.py                   # SQLite schema + helpers
        ├── apollo.py               # Apollo API integration
        ├── verify.py               # Hunter + ZeroBounce fallback
        ├── templates.py            # Email template generation
        └── config.py               # Configuration + API keys
```

## Installation

Requires Python 3.11+.

```bash
git clone https://github.com/ericmay33/Job-Sniper.git
cd Job-Sniper
pip install -e .
sniper --help
```
