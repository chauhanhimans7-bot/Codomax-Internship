"""All SQLite work: users table + per-user expense isolation.

Security model
--------------
* Passwords are hashed with PBKDF2-HMAC-SHA256 (310 000 iterations) + a
  per-user random 32-byte salt stored alongside the hash.  Plain-text
  passwords are never stored or logged.
* Every expense read / write / delete query includes `AND user_id = ?` so
  one authenticated user can never touch another user's rows, even if they
  guess a valid expense id.
* All user input goes through parameterised queries ("?" placeholders) —
  no string interpolation, no SQL-injection risk.
"""

import hashlib
import hmac
import os
import sqlite3
from contextlib import closing
from datetime import date

import pandas as pd

from config import CATEGORIES, DB_PATH, MAX_AMOUNT, MAX_DESC_LENGTH

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")   # enforce FK constraints
    return conn


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Return (hex_hash, hex_salt).  Generate a fresh salt when none given."""
    if salt is None:
        salt = os.urandom(32).hex()
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        310_000,          # OWASP-recommended iteration count for PBKDF2-SHA256
    )
    return key.hex(), salt


# ---------------------------------------------------------------------------
# Schema creation & migration
# ---------------------------------------------------------------------------

def init_db():
    """Create all tables if they do not exist; migrate old single-user DBs."""
    with closing(_connect()) as conn, conn:

        # ── users table ──────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT    NOT NULL,
                salt          TEXT    NOT NULL,
                created_at    TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── expenses table ───────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expense_date TEXT    NOT NULL,
                amount       REAL    NOT NULL,
                description  TEXT    NOT NULL,
                category     TEXT    NOT NULL,
                created_at   TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── migration: add user_id to old single-user expense tables ─────
        # Old rows get user_id = 0 (no matching user) so they stay invisible
        # to every real account — data is preserved but isolated.
        try:
            conn.execute(
                "ALTER TABLE expenses ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass   # column already exists — nothing to do

        # ── index for fast per-user lookups ──────────────────────────────
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expenses_user "
            "ON expenses (user_id, expense_date DESC)"
        )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def create_user(username: str, email: str, password: str) -> tuple[bool, str | int]:
    """Register a new user.

    Returns
    -------
    (True, user_id)          on success
    (False, error_message)   on validation / uniqueness failure
    """
    username = username.strip()
    email    = email.strip().lower()

    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if not username.isalnum() and not all(c.isalnum() or c in "_-" for c in username):
        return False, "Username may only contain letters, numbers, _ and -."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "Please enter a valid email address."

    pw_hash, salt = _hash_password(password)
    try:
        with closing(_connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO users (username, email, password_hash, salt) VALUES (?, ?, ?, ?)",
                (username, email, pw_hash, salt),
            )
            return True, cur.lastrowid
    except sqlite3.IntegrityError as exc:
        msg = str(exc).lower()
        if "username" in msg:
            return False, "That username is already taken — please choose another."
        if "email" in msg:
            return False, "An account with that email already exists."
        return False, "Registration failed. Please try again."


def verify_user(username: str, password: str) -> dict | None:
    """Return a user dict ``{id, username, email}`` if credentials match, else ``None``.

    Timing-safe comparison is used so the response time does not leak
    whether the username exists.
    """
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT id, username, email, password_hash, salt FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()

    if row is None:
        # Still do a dummy hash to prevent username-enumeration via timing
        _hash_password(password, "00" * 32)
        return None

    user_id, uname, email, stored_hash, salt = row
    computed, _ = _hash_password(password, salt)

    # Constant-time comparison
    if not hmac_compare(computed, stored_hash):
        return None

    return {"id": user_id, "username": uname, "email": email}


def hmac_compare(a: str, b: str) -> bool:
    """Constant-time string equality (prevents timing attacks)."""
    return hmac.compare_digest(a.encode(), b.encode())


def get_user_by_id(user_id: int) -> dict | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT id, username, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return {"id": row[0], "username": row[1], "email": row[2]} if row else None


# ---------------------------------------------------------------------------
# Expense validation
# ---------------------------------------------------------------------------

def validate_expense(amount, description, category, expense_date) -> list[str]:
    """Return a list of human-readable error strings (empty = valid)."""
    errors = []
    try:
        amount = float(amount)
        if amount <= 0:
            errors.append("Amount must be greater than 0.")
        elif amount > MAX_AMOUNT:
            errors.append(f"Amount is too large (max ₹{MAX_AMOUNT:,}).")
    except (TypeError, ValueError):
        errors.append("Amount must be a number.")
    if not str(description).strip():
        errors.append("Description cannot be empty.")
    elif len(str(description)) > MAX_DESC_LENGTH:
        errors.append(f"Description is too long (max {MAX_DESC_LENGTH} chars).")
    if category not in CATEGORIES:
        errors.append("Please pick a valid category.")
    if not isinstance(expense_date, date):
        errors.append("Please pick a valid date.")
    elif expense_date > date.today():
        errors.append("Date cannot be in the future.")
    return errors


# ---------------------------------------------------------------------------
# Expense CRUD — every write includes user_id for double-layer isolation
# ---------------------------------------------------------------------------

def add_expense(user_id: int, expense_date: date, amount: float,
                description: str, category: str) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO expenses (user_id, expense_date, amount, description, category) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, expense_date.isoformat(), float(amount),
             description.strip(), category),
        )


def update_expense(user_id: int, expense_id: int, expense_date: date,
                   amount: float, description: str, category: str) -> None:
    """Update only if the expense belongs to this user (AND user_id = ?)."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE expenses "
            "SET expense_date=?, amount=?, description=?, category=? "
            "WHERE id=? AND user_id=?",
            (expense_date.isoformat(), float(amount),
             description.strip(), category, expense_id, user_id),
        )


def delete_expense(user_id: int, expense_id: int) -> None:
    """Delete only if the expense belongs to this user (AND user_id = ?)."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            "DELETE FROM expenses WHERE id=? AND user_id=?",
            (expense_id, user_id),
        )


def get_all_expenses(user_id: int) -> pd.DataFrame:
    """Return this user's expenses as a DataFrame (newest first)."""
    with closing(_connect()) as conn:
        df = pd.read_sql_query(
            "SELECT id, expense_date, amount, description, category "
            "FROM expenses "
            "WHERE user_id = ? "
            "ORDER BY expense_date DESC, id DESC",
            conn,
            params=(user_id,),
        )
    if df.empty:
        # Ensure columns exist even when there is no data
        df = pd.DataFrame(columns=["id", "expense_date", "amount",
                                   "description", "category", "month"])
        return df
    df["expense_date"] = pd.to_datetime(df["expense_date"])
    df["month"] = df["expense_date"].dt.strftime("%Y-%m")
    return df


def get_expense_count(user_id: int) -> int:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id=?", (user_id,)
        ).fetchone()[0]
