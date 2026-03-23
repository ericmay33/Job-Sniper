"""Email draft generation from user-editable templates.json."""

import json
import os

from rich.console import Console

console = Console(force_terminal=True)

TEMPLATES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates.json")

REQUIRED_KEYS = ["applied", "proactive", "followups"]

DEFAULT_TEMPLATES = {
    "applied": {
        "subject": "Quinnipiac CS Senior \u2014 {role} Application",
        "body": (
            "Hi {first_name},\n\n"
            "I'm Eric, a CS senior at Quinnipiac (4.0 GPA, AWS Certified) graduating May 2026. "
            "I just applied for the {role} position and wanted to reach out directly.\n\n"
            "Last summer I interned at Merck building enterprise features with React, TypeScript, "
            "Node, and PostgreSQL. I've also built an AI DevOps agent that auto-generates "
            "Dockerfiles and CI/CD pipelines from any GitHub repo.\n\n"
            "[YOUR \"WHY THEM\" LINE \u2014 e.g., what about {company} specifically excites you]\n\n"
            "Would you be open to a brief chat, or could you point me toward the right person "
            "for this role? I've attached my resume.\n\n"
            "Thanks,\nEric May"
        ),
    },
    "proactive": {
        "subject": "CS New Grad | Merck SWE Intern + AWS Certified \u2014 {company} Interest",
        "body": (
            "Hi {first_name},\n\n"
            "I'm Eric, a CS senior at Quinnipiac (4.0 GPA, AWS Certified) graduating May 2026 "
            "and exploring new grad SWE and infrastructure roles.\n\n"
            "I interned at Merck last summer doing full-stack development with React, TypeScript, "
            "Node, and PostgreSQL. I also built an AI DevOps agent that analyzes GitHub repos and "
            "auto-generates Dockerfiles, CI/CD workflows, and deployment configs.\n\n"
            "[YOUR \"WHY THEM\" LINE \u2014 e.g., what about {company} caught your attention]\n\n"
            "I'd love to learn about any upcoming opportunities on your engineering team. "
            "Resume attached \u2014 happy to chat anytime.\n\n"
            "Thanks,\nEric May"
        ),
    },
    "followups": {
        "1": (
            "Hi {first_name}, just bumping this up \u2014 would love to connect if you have a moment. "
            "Happy to work around your schedule.\n\n"
            "\u2014 Eric"
        ),
        "2": (
            "Hi {first_name}, following up one more time. "
            "[OPTIONAL: Add a new detail \u2014 \"Since my last note, I also completed/launched/earned X.\"]\n\n"
            "Still very interested in {company} \u2014 let me know if there's a better time or person "
            "to reach out to.\n\n"
            "\u2014 Eric"
        ),
        "3": (
            "Hi {first_name}, totally understand if the timing isn't right. "
            "I'll leave the door open \u2014 feel free to reach out anytime. "
            "Wishing you and the team all the best.\n\n"
            "\u2014 Eric"
        ),
    },
}


def _create_default_templates() -> None:
    """Write templates.json with full default content."""
    with open(TEMPLATES_PATH, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_TEMPLATES, f, indent=4, ensure_ascii=False)
    console.print("[green]✓ Created templates.json — edit this file to customize your email templates[/green]")


def _load_templates() -> dict:
    """Load and validate templates.json, creating defaults if needed."""
    if not os.path.exists(TEMPLATES_PATH):
        _create_default_templates()

    with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            console.print("[red]✗ templates.json has invalid JSON — fix it or delete it to regenerate defaults[/red]")
            raise SystemExit(1)

    for key in REQUIRED_KEYS:
        if key not in data:
            console.print(f"[red]✗ templates.json is missing required key '{key}' — fix it or delete it to regenerate defaults[/red]")
            raise SystemExit(1)

    return data


def generate_draft(
    company: str,
    role: str,
    first_name: str,
    contact_title: str,
    applied: bool,
    url: str = "",
    notes: str = "",
) -> tuple[str, str]:
    """Generate (subject, body) tuple from templates."""
    tpl = _load_templates()
    key = "applied" if applied else "proactive"
    variables = {"first_name": first_name, "role": role, "company": company}

    subject = tpl[key]["subject"].format(**variables)
    body = tpl[key]["body"].format(**variables)
    return subject, body


def generate_followup(
    company: str,
    first_name: str,
    original_subject: str,
    followup_number: int,
) -> tuple[str, str]:
    """Generate follow-up (subject, body) tuple."""
    tpl = _load_templates()
    variables = {"first_name": first_name, "company": company}

    subject = f"Re: {original_subject}"
    body = tpl["followups"][str(followup_number)].format(**variables)
    return subject, body
