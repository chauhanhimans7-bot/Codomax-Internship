"""Authentication UI helpers for the AI Expense Tracker.

Renders the Login / Register page when no user is in session state.
All credential verification and hashing lives in database.py.
"""
import importlib
import re

import streamlit as st

import database as db
importlib.reload(db)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def init_session() -> None:
    """Ensure all required session-state keys exist."""
    defaults = {
        "user":    None,   # dict {id, username, email} or None
        "parsed":  None,   # AI-parsed expense dict
        "form_id": 0,      # bumped to reset add-expense form
        "summary": None,   # cached AI summary text
    }
    for key, val in defaults.items():
        st.session_state.setdefault(key, val)


def is_logged_in() -> bool:
    return st.session_state.get("user") is not None


def current_user() -> dict:
    return st.session_state["user"]


def logout() -> None:
    """Clear all session state and return to login screen."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# ---------------------------------------------------------------------------
# Login / Register page
# ---------------------------------------------------------------------------

def _validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def show_auth_page() -> None:
    """Full-page login / register UI.  Calls st.stop() so the caller
    never reaches the main app while the user is unauthenticated."""

    # ── branding ─────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style='text-align:center; padding: 2rem 0 1rem 0'>
            <span style='font-size:3rem'>💰</span>
            <h1 style='margin:0; font-size:2rem'>AI Expense Tracker</h1>
            <p style='color:grey'>Your personal finance coach, powered by AI</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── centered card ────────────────────────────────────────────────────
    _, card, _ = st.columns([1, 1.6, 1])
    with card:
        tab_login, tab_register = st.tabs(["🔑  Sign In", "📝  Create Account"])

        # ── LOGIN ────────────────────────────────────────────────────────
        with tab_login:
            st.markdown("#### Welcome back!")
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Username", placeholder="your_username",
                                         autocomplete="username")
                password = st.text_input("Password", type="password",
                                         placeholder="••••••••",
                                         autocomplete="current-password")
                login_btn = st.form_submit_button(
                    "Sign In", type="primary", use_container_width=True
                )

            if login_btn:
                if not username.strip() or not password:
                    st.error("Please enter both username and password.")
                else:
                    with st.spinner("Verifying…"):
                        user = db.verify_user(username, password)
                    if user:
                        st.session_state.user = user
                        st.success(f"Welcome back, **{user['username']}**! 👋")
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password.")

        # ── REGISTER ─────────────────────────────────────────────────────
        with tab_register:
            st.markdown("#### Create your account")
            with st.form("register_form", clear_on_submit=False):
                new_user  = st.text_input("Username",
                                          placeholder="e.g. john_doe (3+ chars, letters/numbers/_-)",
                                          key="reg_username",
                                          autocomplete="username")
                new_email = st.text_input("Email",
                                          placeholder="you@example.com",
                                          key="reg_email",
                                          autocomplete="email")
                new_pw    = st.text_input("Password",
                                          type="password",
                                          placeholder="Minimum 6 characters",
                                          key="reg_pw",
                                          autocomplete="new-password")
                new_pw2   = st.text_input("Confirm Password",
                                          type="password",
                                          placeholder="Repeat your password",
                                          key="reg_pw2",
                                          autocomplete="new-password")
                reg_btn   = st.form_submit_button(
                    "Create Account", type="primary", use_container_width=True
                )

            if reg_btn:
                # Client-side checks before hitting the DB
                errors = []
                if not new_user.strip():
                    errors.append("Username is required.")
                if not _validate_email(new_email):
                    errors.append("Please enter a valid email address.")
                if len(new_pw) < 6:
                    errors.append("Password must be at least 6 characters.")
                if new_pw != new_pw2:
                    errors.append("Passwords do not match.")

                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    with st.spinner("Creating your account…"):
                        ok, result = db.create_user(new_user, new_email, new_pw)
                    if ok:
                        user = db.verify_user(new_user, new_pw)
                        st.session_state.user = user
                        st.success("🎉 Account created! Welcome aboard!")
                        st.rerun()
                    else:
                        st.error(f"❌ {result}")

    st.stop()   # ← nothing below this runs while unauthenticated
