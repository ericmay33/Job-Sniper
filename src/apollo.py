"""Apollo API integration for contact discovery."""

import requests
from rich.console import Console

import config
import db

console = Console(force_terminal=True)

RECRUITER_KEYWORDS = {"recruiter", "talent acquisition", "recruiting"}


def _is_recruiter_title(title: str) -> bool:
    """Check if a title looks like a recruiter (vs engineering manager)."""
    lower = title.lower()
    return any(kw in lower for kw in RECRUITER_KEYWORDS)


def search_contact(company_name: str) -> dict | None:
    """
    Search Apollo for a recruiter or engineering manager at the given company.

    Returns dict with keys: name, first_name, title, email, linkedin_url
    Returns None if no suitable contact found.
    """
    if not config.APOLLO_API_KEY:
        console.print("[red]✗ Apollo API key not set. Add APOLLO_API_KEY to your .env file[/red]")
        return None

    payload = {
        "api_key": config.APOLLO_API_KEY,
        "q_organization_name": company_name,
        "person_titles": [
            "recruiter",
            "university recruiter",
            "talent acquisition",
            "technical recruiter",
            "engineering manager",
            "hiring manager",
        ],
        "page": 1,
        "per_page": 5,
    }

    try:
        resp = requests.post(
            "https://api.apollo.io/api/v1/mixed_people/search",
            json=payload,
            headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
            timeout=10,
        )
    except requests.RequestException as e:
        console.print(f"[yellow]⚠ Apollo request failed for {company_name}: {e}[/yellow]")
        db.increment_credits("apollo")
        return None

    db.increment_credits("apollo")

    if resp.status_code != 200:
        console.print(f"[yellow]⚠ Apollo returned {resp.status_code} for {company_name}: {resp.text[:200]}[/yellow]")
        return None

    people = resp.json().get("people") or []
    if not people:
        return None

    # Filter to people with emails, sort recruiters first
    with_email = [p for p in people if p.get("email")]
    if not with_email:
        return None

    with_email.sort(key=lambda p: 0 if _is_recruiter_title(p.get("title", "")) else 1)

    best = with_email[0]
    return {
        "name": best.get("name", ""),
        "first_name": best.get("first_name", ""),
        "title": best.get("title", ""),
        "email": best["email"],
        "linkedin_url": best.get("linkedin_url", "") or "",
    }
