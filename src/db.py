"""SQLite schema initialization and all database helper functions."""

import sqlite3
from datetime import datetime

from config import DB_PATH, FOLLOWUP_1_DAYS, FOLLOWUP_2_DAYS, FOLLOWUP_3_DAYS


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Called on every CLI invocation."""
    conn = _connect()
    try:
        conn.executescript("""
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
        """)
        conn.commit()
    finally:
        conn.close()


def add_company(company: str, role: str, url: str, notes: str, applied: bool) -> int:
    """Insert a new company. Returns company id. Raises if duplicate."""
    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT id FROM companies WHERE company LIKE ? LIMIT 1",
            (company,),
        ).fetchone()
        if existing:
            raise sqlite3.IntegrityError(f"Company '{company}' already exists (id={existing['id']})")
        cur = conn.execute(
            """INSERT INTO companies (company, role, url, notes, applied)
               VALUES (?, ?, ?, ?, ?)""",
            (company, role, url, notes, int(applied)),
        )
        company_id = cur.lastrowid
        conn.execute(
            "INSERT INTO outreach_log (company_id, action) VALUES (?, 'queued')",
            (company_id,),
        )
        conn.commit()
        return company_id
    finally:
        conn.close()


def get_queued() -> list[dict]:
    """Return all companies with status 'queued'."""
    return get_by_status("queued")


def get_ready() -> list[dict]:
    """Return all companies with status 'ready'."""
    return get_by_status("ready")


def get_by_status(status: str) -> list[dict]:
    """Return all companies matching a status."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM companies WHERE status = ? ORDER BY id", (status,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_company(company_id: int, **kwargs) -> None:
    """Update arbitrary fields on a company row. Always updates updated_at."""
    if not kwargs:
        return
    kwargs["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [company_id]
    conn = _connect()
    try:
        conn.execute(
            f"UPDATE companies SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
    finally:
        conn.close()


def update_status(company_name: str, new_status: str) -> None:
    """Find company by name (case-insensitive LIKE match), update status.
    If new_status is 'emailed', also set emailed_date to now.
    Log to outreach_log."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM companies WHERE company LIKE ? LIMIT 1",
            (f"%{company_name}%",),
        ).fetchone()
        if row is None:
            raise ValueError(f"No company found matching '{company_name}'")

        now = datetime.now().isoformat()
        updates = {"status": new_status, "updated_at": now}

        if new_status == "emailed":
            updates["emailed_date"] = now
        elif new_status == "followed_up":
            updates["followup_count"] = row["followup_count"] + 1
            updates["last_followup_date"] = now

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [row["id"]]
        conn.execute(f"UPDATE companies SET {set_clause} WHERE id = ?", values)

        action = new_status
        if new_status == "followed_up":
            action = f"followup_{updates['followup_count']}"
        conn.execute(
            "INSERT INTO outreach_log (company_id, action) VALUES (?, ?)",
            (row["id"], action),
        )
        conn.commit()
    finally:
        conn.close()


def get_followups_due() -> list[dict]:
    """Return companies where a follow-up is due based on timing rules."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT * FROM companies
               WHERE status IN ('emailed', 'followed_up')
                 AND followup_count < 3
               ORDER BY id"""
        ).fetchall()

        now = datetime.now()
        due = []

        for row in rows:
            r = dict(row)
            fc = r["followup_count"]

            if fc == 0:
                ref_date = r["emailed_date"]
                threshold = FOLLOWUP_1_DAYS
            else:
                ref_date = r["last_followup_date"]
                threshold = FOLLOWUP_2_DAYS if fc == 1 else FOLLOWUP_3_DAYS

            if ref_date is None:
                continue

            days_since = (now - datetime.fromisoformat(ref_date)).days
            if days_since >= threshold:
                r["days_since"] = days_since
                r["next_followup"] = fc + 1
                due.append(r)

        # Auto-mark dead: followup_count >= 3 and still not replied
        stale_rows = conn.execute(
            """SELECT id FROM companies
               WHERE status IN ('emailed', 'followed_up')
                 AND followup_count >= 3"""
        ).fetchall()
        for sr in stale_rows:
            conn.execute(
                "UPDATE companies SET status = 'dead', updated_at = ? WHERE id = ?",
                (now.isoformat(), sr["id"]),
            )
            conn.execute(
                "INSERT INTO outreach_log (company_id, action) VALUES (?, 'dead')",
                (sr["id"],),
            )
        if stale_rows:
            conn.commit()

        return due
    finally:
        conn.close()


def get_status_counts() -> dict:
    """Return {status: count} for all statuses."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM companies GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}
    finally:
        conn.close()


def get_credit_usage(service: str) -> int:
    """Return credits used this month for a service."""
    month = datetime.now().strftime("%Y-%m")
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT credits_used FROM api_credits WHERE service = ? AND month = ?",
            (service, month),
        ).fetchone()
        return row["credits_used"] if row else 0
    finally:
        conn.close()


def increment_credits(service: str, amount: int = 1) -> None:
    """Increment credit counter for service for current month."""
    month = datetime.now().strftime("%Y-%m")
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO api_credits (service, month, credits_used)
               VALUES (?, ?, ?)
               ON CONFLICT(service, month)
               DO UPDATE SET credits_used = credits_used + ?""",
            (service, month, amount, amount),
        )
        conn.commit()
    finally:
        conn.close()


def get_company_by_id(company_id: int) -> dict | None:
    """Return single company row by id."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def search_company(name: str) -> dict | None:
    """Case-insensitive search for a company by name. Returns first match or None."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM companies WHERE company LIKE ? LIMIT 1",
            (f"%{name}%",),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
