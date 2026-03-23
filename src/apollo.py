"""Apollo API integration for contact discovery."""

import requests

import config
import db

RECRUITER_KEYWORDS = {"recruiter", "talent acquisition", "recruiting"}


def _is_recruiter_title(title: str) -> bool:
    lower = title.lower()
    return any(kw in lower for kw in RECRUITER_KEYWORDS)


def search_contact(company_name: str) -> dict | None:
    """Search Apollo for a recruiter or eng manager. Returns contact dict or None."""
    if not config.APOLLO_API_KEY:
        print("✗ Apollo API key not set. Add APOLLO_API_KEY to your .env file")
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
        print(f"⚠ Apollo request failed for {company_name}: {e}")
        db.increment_credits("apollo")
        return None

    db.increment_credits("apollo")

    if resp.status_code != 200:
        print(f"⚠ Apollo returned {resp.status_code} for {company_name}: {resp.text[:200]}")
        return None

    people = resp.json().get("people") or []
    if not people:
        return None

    with_email = [p for p in people if p.get("email")]
    if not with_email:
        return None

    # Prefer recruiters over eng managers
    with_email.sort(key=lambda p: 0 if _is_recruiter_title(p.get("title", "")) else 1)

    best = with_email[0]
    return {
        "name": best.get("name", ""),
        "first_name": best.get("first_name", ""),
        "title": best.get("title", ""),
        "email": best["email"],
        "linkedin_url": best.get("linkedin_url", "") or "",
    }
