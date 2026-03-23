"""Email verification via Hunter and ZeroBounce fallback chain."""

import requests
from rich.console import Console

import config
import db

console = Console(force_terminal=True)


def _try_hunter(email: str) -> str | None:
    """Verify via Hunter. Returns "verified_hunter" or None to fall through."""
    if not config.HUNTER_API_KEY:
        return None

    if db.get_credit_usage("hunter") >= config.HUNTER_MONTHLY_LIMIT:
        return None

    try:
        resp = requests.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": config.HUNTER_API_KEY},
            timeout=10,
        )
    except requests.RequestException as e:
        console.print(f"[yellow]⚠ Hunter request failed: {e}[/yellow]")
        db.increment_credits("hunter")
        return None

    db.increment_credits("hunter")

    if resp.status_code != 200:
        console.print(f"[yellow]⚠ Hunter returned {resp.status_code}[/yellow]")
        return None

    status = resp.json().get("data", {}).get("status", "")
    if status in ("valid", "accept_all"):
        return "verified_hunter"

    return None


def _try_zerobounce(email: str) -> str | None:
    """Verify via ZeroBounce. Returns "verified_zerobounce" or None to fall through."""
    if not config.ZEROBOUNCE_API_KEY:
        return None

    if db.get_credit_usage("zerobounce") >= config.ZEROBOUNCE_MONTHLY_LIMIT:
        return None

    try:
        resp = requests.get(
            "https://api.zerobounce.net/v2/validate",
            params={"api_key": config.ZEROBOUNCE_API_KEY, "email": email},
            timeout=10,
        )
    except requests.RequestException as e:
        console.print(f"[yellow]⚠ ZeroBounce request failed: {e}[/yellow]")
        db.increment_credits("zerobounce")
        return None

    db.increment_credits("zerobounce")

    if resp.status_code != 200:
        console.print(f"[yellow]⚠ ZeroBounce returned {resp.status_code}[/yellow]")
        return None

    status = resp.json().get("status", "")
    if status in ("valid", "catch-all"):
        return "verified_zerobounce"

    return None


def verify_email(email: str) -> str:
    """
    Run email through Hunter -> ZeroBounce fallback chain.
    Returns: "verified_hunter" | "verified_zerobounce" | "unverified"
    """
    result = _try_hunter(email)
    if result:
        return result

    result = _try_zerobounce(email)
    if result:
        return result

    return "unverified"
