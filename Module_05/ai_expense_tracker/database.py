"""SQLite database operations with strict per-user expense isolation.

Data Isolation Model
--------------------
* Every expense is tied to a specific `user_id`.
* Every SELECT / INSERT / UPDATE / DELETE query is parameterized and strictly
  filtered by `user_id = ?`.
* No user can view, edit, delete, or run AI analysis on another user's expenses.
"""

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
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Schema creation & migration
# ---------------------------------------------------------------------------

def init_db():
    """Create tables if not existing and ensure user-based data isolation."""
    with closing(_connect()) as conn, conn:
        # ── users table ──────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                email      TEXT    DEFAULT '',
                created_at TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── expenses table ───────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                expense_date TEXT    NOT NULL,
                amount       REAL    NOT NULL,
                description  TEXT    NOT NULL,
                category     TEXT    NOT NULL,
                created_at   TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── migration: add user_id column if an older single-user db exists ──
        try:
            conn.execute(
                "ALTER TABLE expenses ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"
            )
        except sqlite3.OperationalError:
            pass

        # ── ensure at least one default user exists ──────────────────────
        first_user = conn.execute("SELECT id, username FROM users ORDER BY id ASC LIMIT 1").fetchone()
        if not first_user:
            cur = conn.execute(
                "INSERT INTO users (username, email, password_hash, salt) VALUES (?, ?, '', '')",
                ("Primary User", "user@local"),
            )
            default_id = cur.lastrowid
        else:
            default_id = first_user[0]

        # ── reassign any legacy unassigned expenses (user_id = 0) to default user ──
        conn.execute("UPDATE expenses SET user_id = ? WHERE user_id = 0", (default_id,))

        # ── index for fast isolated queries ──────────────────────────────
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expenses_user "
            "ON expenses (user_id, expense_date DESC)"
        )


# ---------------------------------------------------------------------------
# User management (isolated workspaces without password barriers)
# ---------------------------------------------------------------------------

def get_or_create_user(username: str) -> dict:
    """Find or create a user by username. Case-insensitive."""
    clean_name = username.strip() or "Primary User"
    with closing(_connect()) as conn, conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE username = ? COLLATE NOCASE",
            (clean_name,),
        ).fetchone()
        if row:
            return {"id": row[0], "username": row[1]}

        # Check if users table has password_hash column
        cols = [c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "password_hash" in cols:
            cur = conn.execute(
                "INSERT INTO users (username, email, password_hash, salt) VALUES (?, ?, '', '')",
                (clean_name, f"{clean_name.lower()}@local"),
            )
        else:
            cur = conn.execute(
                "INSERT INTO users (username, email) VALUES (?, ?)",
                (clean_name, f"{clean_name.lower()}@local"),
            )
        return {"id": cur.lastrowid, "username": clean_name}


def get_all_users() -> list[dict]:
    """Return all existing users."""
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT id, username FROM users ORDER BY id ASC"
        ).fetchall()
    return [{"id": r[0], "username": r[1]} for r in rows]


def get_user_by_id(user_id: int) -> dict | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return {"id": row[0], "username": row[1]} if row else None


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
# Expense CRUD — strictly isolated by user_id
# ---------------------------------------------------------------------------

def add_expense(user_id: int, expense_date: date, amount: float,
                description: str, category: str) -> None:
    """Insert an expense strictly owned by user_id."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO expenses (user_id, expense_date, amount, description, category) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, expense_date.isoformat(), float(amount),
             description.strip(), category),
        )


def update_expense(user_id: int, expense_id: int, expense_date: date,
                   amount: float, description: str, category: str) -> None:
    """Update only if the expense belongs to user_id."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE expenses "
            "SET expense_date=?, amount=?, description=?, category=? "
            "WHERE id=? AND user_id=?",
            (expense_date.isoformat(), float(amount),
             description.strip(), category, expense_id, user_id),
        )


def delete_expense(user_id: int, expense_id: int) -> None:
    """Delete only if the expense belongs to user_id."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            "DELETE FROM expenses WHERE id=? AND user_id=?",
            (expense_id, user_id),
        )


def get_all_expenses(user_id: int) -> pd.DataFrame:
    """Return only this user's expenses as a DataFrame (newest first)."""
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
        return pd.DataFrame(columns=["id", "expense_date", "amount",
                                     "description", "category", "month"])
    df["expense_date"] = pd.to_datetime(df["expense_date"])
    df["month"] = df["expense_date"].dt.strftime("%Y-%m")
    return df


def get_expense_count(user_id: int) -> int:
    """Count expenses belonging exclusively to this user."""
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id=?", (user_id,)
        ).fetchone()[0]
