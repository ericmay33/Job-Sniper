"""Rich display functions — all terminal rendering lives here."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console(force_terminal=True)

STATUS_COLORS = {
    "queued": "blue",
    "ready": "cyan",
    "emailed": "yellow",
    "followed_up": "yellow",
    "replied": "green",
    "interview": "green",
    "dead": "red",
    "stale": "red",
}


def _verification_markup(vs: str | None) -> str:
    if vs and vs.startswith("verified"):
        source = vs.replace("verified_", "")
        return f"[green]\u2713 {source}[/green]"
    if vs == "unverified":
        return "[yellow]\u26a0 unverified[/yellow]"
    return "[dim]\u2014[/dim]"


def show_drafts_table(drafts: list[dict]) -> None:
    table = Table(title="Ready Drafts")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Company", style="cyan")
    table.add_column("Contact")
    table.add_column("Verified")
    table.add_column("Draft Preview", max_width=60)

    for i, c in enumerate(drafts, 1):
        table.add_row(
            str(i),
            c["company"],
            c["contact_name"] or "\u2014",
            _verification_markup(c["verification_status"]),
            (c["draft_body"] or "")[:60],
        )

    console.print(table)


def show_draft_detail(c: dict, number: int) -> None:
    vs = c["verification_status"]
    template_type = "A (applied)" if c["applied"] else "B (proactive)"

    body = "\n".join([
        f"[bold]\u2550\u2550\u2550 {c['company']} \u2550\u2550\u2550[/bold]",
        f"Contact: {c['contact_name'] or 'Unknown'} ({c['contact_title'] or 'Unknown'})",
        f"LinkedIn: {c['contact_linkedin'] or '\u2014'}",
        f"Email: {c['contact_email'] or '\u2014'}  |  Verified: {_verification_markup(vs)}",
        f"Template: {template_type}",
        "",
        f"[bold]Subject:[/bold] {c['draft_subject'] or '\u2014'}",
        "",
        c["draft_body"] or "(no draft body)",
    ])

    console.print(Panel(body, title=f"Draft #{number}", border_style="blue", padding=(1, 2)))

    reminders = ["[blue]\u2139[/blue]  Check LinkedIn before sending"]
    if vs == "unverified" or vs is None:
        reminders.append("[yellow]\u26a0[/yellow]  Hover in Gmail to verify \u2014 email is unverified")
    console.print(Panel("\n".join(reminders), title="Reminders", border_style="yellow"))


def show_followups_table(followups: list[dict]) -> None:
    table = Table(title="Follow-ups Due")
    table.add_column("Company", style="cyan")
    table.add_column("Contact")
    table.add_column("Days Since", justify="right")
    table.add_column("Follow-up #")
    table.add_column("Draft Preview", max_width=60)

    for c in followups:
        fu_num = c["next_followup"]
        if fu_num == 3:
            label = "[red]3rd \u2014 final[/red]"
        elif fu_num == 2:
            label = "[yellow]2nd (send now)[/yellow]"
        else:
            label = "[green]1st (send now)[/green]"

        table.add_row(
            c["company"],
            c["contact_name"] or "\u2014",
            str(c["days_since"]),
            label,
            (c["followup_body"] or "")[:60],
        )

    console.print(table)


def show_status_dashboard(counts: dict, credits: dict) -> None:
    all_statuses = ["queued", "ready", "emailed", "followed_up", "replied", "interview", "stale", "dead"]

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="bold")
    table.add_column("Value", justify="right")

    for s in all_statuses:
        color = STATUS_COLORS.get(s, "white")
        label = s.replace("_", " ").title()
        table.add_row(f"[{color}]{label}[/{color}]", f"[{color}]{counts.get(s, 0)}[/{color}]")

    total = sum(counts.get(s, 0) for s in all_statuses)
    table.add_row("", "")
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")

    denominator = sum(counts.get(s, 0) for s in ["emailed", "followed_up", "replied", "interview", "dead"])
    numerator = sum(counts.get(s, 0) for s in ["replied", "interview"])
    reply_rate = (numerator / denominator * 100) if denominator > 0 else 0.0
    table.add_row("Reply Rate", f"{reply_rate:.1f}%")

    table.add_row("", "")
    table.add_row(
        "API Credits",
        f"Apollo: {10000 - credits.get('apollo', 0)}  |  "
        f"Hunter: {25 - credits.get('hunter', 0)}/25  |  "
        f"ZB: {100 - credits.get('zerobounce', 0)}/100",
    )

    console.print(Panel(table, title="JOB SNIPER \u2014 DASHBOARD", border_style="blue", padding=(1, 2)))


def show_process_preview(queued: list[dict]) -> None:
    table = Table(title="Dry Run \u2014 Queued Companies")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Company", style="cyan")
    table.add_column("Role")
    table.add_column("Contact", style="dim")
    table.add_column("Email", style="dim")
    table.add_column("Verified", style="dim")

    for i, c in enumerate(queued, 1):
        table.add_row(str(i), c["company"], c["role"] or "\u2014", "pending", "pending", "pending")

    console.print(table)
