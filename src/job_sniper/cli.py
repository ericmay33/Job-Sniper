#!/usr/bin/env python3
"""Job Sniper CLI — cold outreach pipeline for job search."""

import sqlite3
import sys

import typer
from rich.console import Console

from . import apollo
from . import db
from . import display
from . import templates
from . import verify

app = typer.Typer(help="Job Sniper - Cold outreach pipeline for job search")
drafts_app = typer.Typer(help="List ready drafts, or use 'drafts show #' for full detail")
app.add_typer(drafts_app, name="drafts")

console = Console(force_terminal=True)

VALID_STATUSES = ["emailed", "followed_up", "replied", "interview", "dead", "stale"]


@app.callback()
def init():
    """Initialize database on every CLI invocation."""
    db.init_db()


@app.command()
def add(
    company: str = typer.Option(..., "--company", "-c", help="Company name"),
    role: str = typer.Option("", "--role", "-r", help="Role title"),
    url: str = typer.Option("", "--url", "-u", help="Job posting URL"),
    notes: str = typer.Option("", "--notes", "-n", help="Notes about the company"),
    applied: bool = typer.Option(False, "--applied", "-a", help="Flag: already applied to this role"),
):
    """Add a company to the outreach queue."""
    try:
        db.add_company(company, role, url, notes, applied)
    except sqlite3.IntegrityError:
        console.print(f"[red]\u2717 '{company}' is already in the pipeline.[/red]")
        raise typer.Exit(1)

    funnel = "(Funnel A \u2014 applied)" if applied else "(Funnel B \u2014 proactive)"
    role_display = f" ({role})" if role else ""
    console.print(f"[green]\u2713 Queued: {company}{role_display}[/green] {funnel}")


@app.command()
def process(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without using API credits"),
):
    """Batch process: Apollo lookup \u2192 verify \u2192 generate drafts."""
    queued = db.get_queued()
    if not queued:
        console.print("No companies in queue. Run 'sniper add' first.")
        return

    if dry_run:
        display.show_process_preview(queued)
        return

    found = 0
    for c in queued:
        console.print(f"  Processing {c['company']}...", end=" ")
        contact = apollo.search_contact(c["company"])

        if contact is None:
            console.print(f"\n[yellow]\u26a0 No contact found for {c['company']} \u2014 try LinkedIn manually[/yellow]")
            continue

        db.update_company(
            c["id"],
            contact_name=contact["name"],
            contact_title=contact["title"],
            contact_email=contact["email"],
            contact_linkedin=contact["linkedin_url"],
        )
        found += 1
        console.print(f"[green]\u2713 {contact['name']} ({contact['title']})[/green]")

        vstatus = verify.verify_email(contact["email"])
        db.update_company(c["id"], verification_status=vstatus)
        if vstatus.startswith("verified"):
            console.print(f"    [green]\u2713 verified via {vstatus.replace('verified_', '')}[/green]")
        else:
            console.print("    [yellow]\u26a0 unverified[/yellow]")

        subject, body = templates.generate_draft(
            company=c["company"],
            role=c["role"] or "",
            first_name=contact["first_name"],
            contact_title=contact["title"],
            applied=bool(c["applied"]),
            url=c["url"] or "",
            notes=c["notes"] or "",
        )
        db.update_company(c["id"], draft_subject=subject, draft_body=body, status="ready")
        console.print("    [blue]\U0001f4dd Draft generated[/blue]")

    console.print(f"\nDone. Found contacts for {found}/{len(queued)} companies.")


@drafts_app.callback(invoke_without_command=True)
def drafts_list(ctx: typer.Context):
    """Show all ready-to-send email drafts."""
    if ctx.invoked_subcommand is not None:
        return

    ready = db.get_ready()
    if not ready:
        console.print("No drafts ready. Run 'sniper process' first.")
        return

    display.show_drafts_table(ready)


@drafts_app.command("show")
def drafts_show(
    number: int = typer.Argument(..., help="Draft number from the drafts table (1-based)"),
):
    """Show full draft with LinkedIn URL, verification, and copy to clipboard."""
    ready = db.get_ready()
    if not ready:
        console.print("No drafts ready. Run 'sniper process' first.")
        raise typer.Exit(1)

    if number < 1 or number > len(ready):
        console.print(f"[red]Invalid draft number. Choose 1\u2013{len(ready)}.[/red]")
        raise typer.Exit(1)

    c = ready[number - 1]
    display.show_draft_detail(c, number)

    body = c["draft_body"] or ""
    if body:
        try:
            import pyperclip
            pyperclip.copy(body)
            console.print("[green]Draft copied to clipboard[/green]")
        except Exception:
            console.print("[dim]Could not copy to clipboard \u2014 copy the draft manually.[/dim]")


@app.command()
def followups():
    """Show overdue follow-ups with auto-generated drafts."""
    due = db.get_followups_due()
    if not due:
        console.print("No follow-ups due right now.")
        return

    for c in due:
        _, fu_body = templates.generate_followup(
            company=c["company"],
            first_name=c["contact_name"].split()[0] if c["contact_name"] else "",
            original_subject=c["draft_subject"] or "",
            followup_number=c["next_followup"],
        )
        c["followup_body"] = fu_body

    display.show_followups_table(due)


@app.command()
def status():
    """Show outreach dashboard with stats and API credits."""
    counts = db.get_status_counts()
    credits = {
        "apollo": db.get_credit_usage("apollo"),
        "hunter": db.get_credit_usage("hunter"),
        "zerobounce": db.get_credit_usage("zerobounce"),
    }
    display.show_status_dashboard(counts, credits)


@app.command()
def update(
    company: str = typer.Argument(..., help="Company name (partial match OK)"),
    status: str = typer.Option(..., "--status", "-s", help="New status: emailed, followed_up, replied, interview, dead, stale"),
):
    """Update a company's outreach status."""
    if status not in VALID_STATUSES:
        console.print(f"[red]Invalid status '{status}'. Must be one of: {', '.join(VALID_STATUSES)}[/red]")
        raise typer.Exit(1)

    match = db.search_company(company)
    if match is None:
        console.print(f"[red]\u2717 No company found matching '{company}'. Check spelling or try a shorter name.[/red]")
        raise typer.Exit(1)

    try:
        db.update_status(match["company"], status)
    except ValueError as e:
        console.print(f"[red]\u2717 {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]\u2713 {match['company']} \u2192 {status}[/green]")


def main():
    """Entry point: no args → interactive shell, otherwise → Typer CLI."""
    if len(sys.argv) <= 1:
        from .shell import run_shell
        run_shell()
    else:
        app()


if __name__ == "__main__":
    main()
