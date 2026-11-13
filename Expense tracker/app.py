"""AI Expense Tracker — multi-user Streamlit UI.

Run with:   streamlit run app.py

Architecture
------------
* auth.py     – login / register UI + session helpers
* database.py – SQLite with per-user data isolation
* ai_helper.py– Groq LLM integration with keyword fallback
* charts.py   – Plotly chart builders
* config.py   – shared settings
"""
from datetime import date
import importlib

import streamlit as st

import ai_helper as ai
import auth
import charts
import database as db
from config import CATEGORIES, CURRENCY

importlib.reload(db)
importlib.reload(auth)

# ── page config (must be FIRST Streamlit call) ───────────────────────────────
st.set_page_config(
    page_title="AI Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── initialise DB + session ───────────────────────────────────────────────────
db.init_db()
auth.init_session()

# ── auth gate: redirect to login if not signed in ────────────────────────────
if not auth.is_logged_in():
    auth.show_auth_page()   # calls st.stop() internally

# ── from here the user is guaranteed to be logged in ─────────────────────────
user    = auth.current_user()
user_id = user["id"]

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## 👤 {user['username']}")
    st.caption(f"📧 {user['email']}")
    st.divider()

    expense_count = db.get_expense_count(user_id)
    st.metric("Your expenses", expense_count)
    st.divider()

    if not ai.ai_available():
        st.warning(
            "⚠️ No Groq API key found.\n\n"
            "AI features are running on keyword fallback.\n"
            "Add `GROQ_API_KEY` to your `.env` file.",
            icon="🤖",
        )
        st.divider()

    if st.button("🚪 Sign Out", use_container_width=True, type="secondary"):
        auth.logout()

# ── utilities ─────────────────────────────────────────────────────────────────

def money(value: float) -> str:
    return f"{CURRENCY}{value:,.0f}"


def show_errors(errors: list[str]) -> None:
    for e in errors:
        st.error(e)


# ── load this user's data ─────────────────────────────────────────────────────
st.title("💰 AI Expense Tracker")
df = db.get_all_expenses(user_id)

tab_dash, tab_add, tab_manage, tab_ai = st.tabs(
    ["📊 Dashboard", "➕ Add Expense", "🗂️ Manage", "🤖 AI Insights"]
)

# ═══════════════════════════════════════════════════════════════ Dashboard ════
with tab_dash:
    if df.empty:
        st.info(
            "👋 No expenses yet, **{}**!  "
            "Head over to **➕ Add Expense** to log your first one.".format(
                user["username"]
            )
        )
    else:
        this_month  = date.today().strftime("%Y-%m")
        month_total = df.loc[df["month"] == this_month, "amount"].sum()
        top_cat     = df.groupby("category")["amount"].sum().idxmax()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total spent",      money(df["amount"].sum()))
        c2.metric("This month",       money(month_total))
        c3.metric("Avg per expense",  money(df["amount"].mean()))
        c4.metric("Top category",     top_cat)

        left, right = st.columns(2)
        left.plotly_chart(charts.category_bar(df),  use_container_width=True)
        right.plotly_chart(charts.category_pie(df), use_container_width=True)

        mode = st.radio("Trend view", ["Monthly", "Daily"], horizontal=True)
        st.plotly_chart(charts.spending_trend(df, mode), use_container_width=True)

        st.subheader("Monthly & category breakdown")
        m1, m2 = st.columns(2)
        monthly = (
            df.groupby("month", as_index=False)["amount"]
            .sum()
            .sort_values("month", ascending=False)
        )
        m1.dataframe(
            monthly.rename(columns={"month": "Month", "amount": "Total (₹)"}),
            hide_index=True,
            use_container_width=True,
        )
        cat = (
            df.groupby("category", as_index=False)["amount"]
            .sum()
            .sort_values("amount", ascending=False)
        )
        m2.dataframe(
            cat.rename(columns={"category": "Category", "amount": "Total (₹)"}),
            hide_index=True,
            use_container_width=True,
        )

# ════════════════════════════════════════════════════════════ Add Expense ════
with tab_add:
    st.subheader("✨ Type it naturally")
    text = st.text_input(
        "Describe your expense in plain English",
        placeholder="e.g. Spent ₹250 on lunch yesterday",
        key="nl_text",
    )
    if st.button("🤖 Parse with AI", use_container_width=False):
        if not text.strip():
            st.warning("Type something first, e.g. 'Paid ₹1200 for electricity bill'.")
        else:
            with st.spinner("Reading your expense…"):
                st.session_state.parsed   = ai.parse_expense(text)
                st.session_state.form_id += 1
            if st.session_state.parsed["source"] == "fallback":
                st.warning(
                    "AI was unavailable — simple keyword rules were used. "
                    "Please double-check the values below."
                )

    parsed   = st.session_state.parsed
    defaults = parsed or {
        "amount":   0.0,
        "description": "",
        "category": "Food & Dining",
        "date":     date.today(),
    }

    st.subheader("✅ Review & save" if parsed else "Or add manually")
    fid = st.session_state.form_id

    with st.form(f"add_form_{fid}"):
        a1, a2 = st.columns(2)
        amount = a1.number_input(
            f"Amount ({CURRENCY})", min_value=0.0, step=10.0,
            value=float(defaults["amount"]), key=f"amt_{fid}",
        )
        exp_date = a2.date_input(
            "Date", value=defaults["date"],
            max_value=date.today(), key=f"date_{fid}",
        )
        desc     = st.text_input("Description", value=defaults["description"], key=f"desc_{fid}")
        cat_idx  = CATEGORIES.index(defaults["category"])
        category = st.selectbox("Category", CATEGORIES, index=cat_idx, key=f"cat_{fid}")
        auto_cat = st.checkbox(
            "Let AI pick the category from the description",
            value=not bool(parsed),
            key=f"auto_{fid}",
        )
        submitted = st.form_submit_button("💾 Save expense", type="primary")

    if submitted:
        if auto_cat and desc.strip():
            category = ai.categorize(desc)
        errors = db.validate_expense(amount, desc, category, exp_date)
        if errors:
            show_errors(errors)
        else:
            try:
                db.add_expense(user_id, exp_date, amount, desc, category)
                st.session_state.parsed   = None
                st.session_state.form_id += 1
                st.session_state.summary  = None
                st.toast(f"Saved {money(amount)} under {category} ✅")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save the expense: {exc}")

# ══════════════════════════════════════════════════════════════════ Manage ════
with tab_manage:
    if df.empty:
        st.info("Nothing to manage yet — add some expenses first.")
    else:
        display = df[["id", "expense_date", "amount", "description", "category"]].copy()
        display["expense_date"] = display["expense_date"].dt.date
        st.dataframe(display, hide_index=True, use_container_width=True)

        st.subheader("Edit or delete")
        labels = {
            int(r.id): (
                f"#{r.id} │ {r.expense_date:%d %b %Y} │ "
                f"{money(r.amount)} │ {r.description}"
            )
            for r in df.itertuples()
        }
        chosen = st.selectbox("Pick an expense to edit / delete",
                              list(labels), format_func=labels.get)
        row = df[df["id"] == chosen].iloc[0]

        with st.form(f"edit_form_{chosen}"):
            e1, e2 = st.columns(2)
            new_amount = e1.number_input(
                f"Amount ({CURRENCY})", min_value=0.0, step=10.0,
                value=float(row["amount"]),
            )
            new_date = e2.date_input(
                "Date", value=row["expense_date"].date(), max_value=date.today()
            )
            new_desc = st.text_input("Description", value=row["description"])
            new_cat  = st.selectbox(
                "Category", CATEGORIES,
                index=CATEGORIES.index(row["category"]),
            )
            save = st.form_submit_button("💾 Update", type="primary")

        if save:
            errors = db.validate_expense(new_amount, new_desc, new_cat, new_date)
            if errors:
                show_errors(errors)
            else:
                db.update_expense(user_id, chosen, new_date, new_amount, new_desc, new_cat)
                st.session_state.summary = None
                st.toast("Expense updated ✅")
                st.rerun()

        st.divider()
        confirm = st.checkbox("⚠️ I understand that deleting is permanent")
        if st.button("🗑️ Delete this expense", disabled=not confirm, type="secondary"):
            db.delete_expense(user_id, chosen)
            st.session_state.summary = None
            st.toast("Expense deleted 🗑️")
            st.rerun()

# ══════════════════════════════════════════════════════════════ AI Insights ════
with tab_ai:
    st.subheader("🤖 Your spending coach")
    st.caption(
        "Only totals and your 5 largest expenses are sent to the AI — "
        "no personal transaction details leave your device."
    )
    if df.empty:
        st.info("Add some expenses first to unlock AI insights.")
    else:
        if st.button("✨ Generate summary & saving tips", type="primary"):
            with st.spinner("Analysing your spending…"):
                st.session_state.summary = ai.generate_summary(df, CURRENCY)
        if st.session_state.summary:
            st.markdown(st.session_state.summary)
