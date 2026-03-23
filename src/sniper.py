#!/usr/bin/env python3
"""Job Sniper CLI entry point — all Typer commands live here."""

import os
import sqlite3
import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import apollo
import db
import templates
import verify

app = typer.Typer(help="Job Sniper - Cold outreach pipeline for job search")
drafts_app = typer.Typer(help="Manage email drafts")
app.add_typer(drafts_app, name="drafts")

console = Console(force_terminal=True)

VALID_STATUSES = ["emailed", "followed_up", "replied", "interview", "dead", "stale"]


@app.callback()
def init():
    """Initialize database on every CLI invocation."""
    db.init_db()


# ── sniper add ───────────────────────────────────────────────────────────────

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
        console.print(f"[red]✗ '{company}' is already in the pipeline.[/red]")
        raise typer.Exit(1)

    funnel = "(Funnel A — applied)" if applied else "(Funnel B — proactive)"
    role_display = f" ({role})" if role else ""
    console.print(f"[green]✓ Queued: {company}{role_display}[/green] {funnel}")


# ── sniper process ───────────────────────────────────────────────────────────

@app.command()
def process(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without using API credits"),
):
    """Batch process: Apollo lookup → verify → generate drafts."""
    queued = db.get_queued()
    if not queued:
        console.print("No companies in queue. Run 'sniper add' first.")
        return

    if dry_run:
        table = Table(title="Dry Run — Queued Companies")
        table.add_column("#", style="dim", justify="right")
        table.add_column("Company", style="cyan")
        table.add_column("Role")
        table.add_column("Contact", style="dim")
        table.add_column("Email", style="dim")
        table.add_column("Verified", style="dim")

        for i, c in enumerate(queued, 1):
            table.add_row(
                str(i),
                c["company"],
                c["role"] or "—",
                "pending",
                "pending",
                "pending",
            )
        console.print(table)
    else:
        found = 0
        for c in queued:
            console.print(f"  Processing {c['company']}...", end=" ")
            contact = apollo.search_contact(c["company"])

            if contact is None:
                console.print(f"\n[yellow]⚠ No contact found for {c['company']} — try LinkedIn manually[/yellow]")
                continue

            db.update_company(
                c["id"],
                contact_name=contact["name"],
                contact_title=contact["title"],
                contact_email=contact["email"],
                contact_linkedin=contact["linkedin_url"],
            )
            found += 1
            console.print(f"[green]✓ {contact['name']} ({contact['title']})[/green]")

            # Verify email
            vstatus = verify.verify_email(contact["email"])
            db.update_company(c["id"], verification_status=vstatus)
            if vstatus.startswith("verified"):
                source = vstatus.replace("verified_", "")
                console.print(f"    [green]✓ verified via {source}[/green]")
            else:
                console.print(f"    [yellow]⚠ unverified[/yellow]")

            # Generate draft
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
            console.print("    [blue]📝 Draft generated[/blue]")

        console.print(f"\nDone. Found contacts for {found}/{len(queued)} companies.")


# ── sniper drafts (sub-group) ───────────────────────────────────────────────

@drafts_app.callback(invoke_without_command=True)
def drafts_list(ctx: typer.Context):
    """Show all ready-to-send email drafts."""
    if ctx.invoked_subcommand is not None:
        return

    ready = db.get_ready()
    if not ready:
        console.print("No drafts ready. Run 'sniper process' first.")
        return

    table = Table(title="Ready Drafts")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Company", style="cyan")
    table.add_column("Contact")
    table.add_column("Verified")
    table.add_column("Draft Preview", max_width=60)

    for i, c in enumerate(ready, 1):
        vs = c["verification_status"]
        if vs and vs.startswith("verified"):
            source = vs.replace("verified_", "")
            verified = f"[green]✓ {source}[/green]"
        elif vs == "unverified":
            verified = "[yellow]⚠ unverified[/yellow]"
        else:
            verified = "[dim]—[/dim]"

        preview = (c["draft_body"] or "")[:60]
        contact = c["contact_name"] or "—"
        table.add_row(str(i), c["company"], contact, verified, preview)

    console.print(table)


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
        console.print(f"[red]Invalid draft number. Choose 1–{len(ready)}.[/red]")
        raise typer.Exit(1)

    c = ready[number - 1]

    # Verification display
    vs = c["verification_status"]
    if vs and vs.startswith("verified"):
        source = vs.replace("verified_", "")
        ver_line = f"[green]✓ {source}[/green]"
    elif vs == "unverified":
        ver_line = "[yellow]⚠ unverified[/yellow]"
    else:
        ver_line = "[dim]—[/dim]"

    template_type = "A (applied)" if c["applied"] else "B (proactive)"

    header_lines = [
        f"[bold]{c['company']}[/bold] — {c['contact_name'] or 'Unknown'} ({c['contact_title'] or 'Unknown'})",
        f"LinkedIn: {c['contact_linkedin'] or '—'}",
        f"Email: {c['contact_email'] or '—'}  |  Verified: {ver_line}",
        f"Template: {template_type}",
        "",
        f"[bold]Subject:[/bold] {c['draft_subject'] or '—'}",
        "",
        c["draft_body"] or "(no draft body)",
    ]

    panel = Panel(
        "\n".join(header_lines),
        title=f"Draft #{number}",
        border_style="blue",
        padding=(1, 2),
    )
    console.print(panel)

    # Reminder box
    reminders = ["Click LinkedIn link above to confirm they still work there"]
    if vs == "unverified" or vs is None:
        reminders.append("Paste email into Gmail compose, hover to check for profile picture")
    console.print(Panel("\n".join(reminders), title="Reminders", border_style="yellow"))

    # Clipboard copy
    body = c["draft_body"] or ""
    if body:
        try:
            import pyperclip
            pyperclip.copy(body)
            console.print("[green]📋 Draft copied to clipboard[/green]")
        except Exception:
            console.print("[dim]Could not copy to clipboard — copy the draft manually.[/dim]")


# ── sniper followups ─────────────────────────────────────────────────────────

@app.command()
def followups():
    """Show overdue follow-ups with auto-generated drafts."""
    due = db.get_followups_due()
    if not due:
        console.print("No follow-ups due right now.")
        return

    table = Table(title="Follow-ups Due")
    table.add_column("Company", style="cyan")
    table.add_column("Contact")
    table.add_column("Days Since", justify="right")
    table.add_column("Follow-up #")
    table.add_column("Draft Preview", max_width=60)

    for c in due:
        fu_num = c["next_followup"]
        if fu_num == 3:
            label = "3rd — final"
        elif fu_num == 2:
            label = "2nd (send now)"
        else:
            label = "1st (send now)"

        _, fu_body = templates.generate_followup(
            company=c["company"],
            first_name=c["contact_name"].split()[0] if c["contact_name"] else "",
            original_subject=c["draft_subject"] or "",
            followup_number=fu_num,
        )
        preview = fu_body[:60]

        table.add_row(
            c["company"],
            c["contact_name"] or "—",
            str(c["days_since"]),
            label,
            preview,
        )

    console.print(table)


# ── sniper status ────────────────────────────────────────────────────────────

@app.command()
def status():
    """Show outreach dashboard with stats and API credits."""
    counts = db.get_status_counts()
    apollo_used = db.get_credit_usage("apollo")
    hunter_used = db.get_credit_usage("hunter")
    zb_used = db.get_credit_usage("zerobounce")

    all_statuses = ["queued", "ready", "emailed", "followed_up", "replied", "interview", "stale", "dead"]

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="bold")
    table.add_column("Value", justify="right")

    for s in all_statuses:
        table.add_row(s.replace("_", " ").title(), str(counts.get(s, 0)))

    total = sum(counts.get(s, 0) for s in all_statuses)
    table.add_row("", "")
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")

    denominator = sum(counts.get(s, 0) for s in ["emailed", "followed_up", "replied", "interview", "dead"])
    numerator = sum(counts.get(s, 0) for s in ["replied", "interview"])
    reply_rate = (numerator / denominator * 100) if denominator > 0 else 0.0
    table.add_row("Reply Rate", f"{reply_rate:.1f}%")

    table.add_row("", "")
    credits_line = (
        f"Apollo: {10000 - apollo_used}  |  "
        f"Hunter: {25 - hunter_used}  |  "
        f"ZB: {100 - zb_used}"
    )
    table.add_row("API Credits", credits_line)

    panel = Panel(table, title="JOB SNIPER — DASHBOARD", border_style="blue", padding=(1, 2))
    console.print(panel)


# ── sniper update ────────────────────────────────────────────────────────────

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
        console.print(f"[red]✗ No company found matching '{company}'. Check spelling or try a shorter name.[/red]")
        raise typer.Exit(1)

    try:
        db.update_status(match["company"], status)
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓ {match['company']} → {status}[/green]")


# ── entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
