"""Email verification via Hunter and ZeroBounce fallback chain."""

import requests

import config
import db


def _try_hunter(email: str) -> str | None:
    """Returns "verified_hunter" or None to fall through."""
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
        print(f"⚠ Hunter request failed: {e}")
        db.increment_credits("hunter")
        return None

    db.increment_credits("hunter")

    if resp.status_code != 200:
        print(f"⚠ Hunter returned {resp.status_code}")
        return None

    status = resp.json().get("data", {}).get("status", "")
    if status in ("valid", "accept_all"):
        return "verified_hunter"
    return None


def _try_zerobounce(email: str) -> str | None:
    """Returns "verified_zerobounce" or None to fall through."""
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
        print(f"⚠ ZeroBounce request failed: {e}")
        db.increment_credits("zerobounce")
        return None

    db.increment_credits("zerobounce")

    if resp.status_code != 200:
        print(f"⚠ ZeroBounce returned {resp.status_code}")
        return None

    status = resp.json().get("status", "")
    if status in ("valid", "catch-all"):
        return "verified_zerobounce"
    return None


def verify_email(email: str) -> str:
    """Hunter → ZeroBounce fallback. Returns verification status string."""
    return _try_hunter(email) or _try_zerobounce(email) or "unverified"
