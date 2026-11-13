"""AI Expense Tracker — Multi-User Isolated Streamlit Application.

Run with:   streamlit run app.py

Features:
- Instant access: No login/password barriers.
- Strict data isolation: Every user/workspace only sees and manages their own expenses.
- Switch or create isolated user profiles from the sidebar.
- Preserves active user via query parameter (?u=Username) across reloads and bookmarks.
- Groq AI-powered parsing, automatic categorization, and insights.
"""
from datetime import date
import importlib

import streamlit as st

import ai_helper as ai
import charts
import database as db
from config import CATEGORIES, CURRENCY

# Reload database module so file modifications take effect immediately
importlib.reload(db)

# ── page config (must be FIRST Streamlit call) ───────────────────────────────
st.set_page_config(
    page_title="AI Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── initialise database ───────────────────────────────────────────────────────
db.init_db()

# ── session state defaults ────────────────────────────────────────────────────
st.session_state.setdefault("parsed", None)      # result of AI parsing
st.session_state.setdefault("form_id", 0)        # bump to reset the add form
st.session_state.setdefault("summary", None)     # cached AI summary

# ── user resolution (isolated workspaces without login walls) ─────────────────
users = db.get_all_users()
if not users:
    db.get_or_create_user("Primary User")
    users = db.get_all_users()

user_names = [u["username"] for u in users]

# Check URL query param ?u=...
query_param_user = st.query_params.get("u")
if query_param_user and query_param_user in user_names:
    active_idx = user_names.index(query_param_user)
elif "active_user_name" in st.session_state and st.session_state["active_user_name"] in user_names:
    active_idx = user_names.index(st.session_state["active_user_name"])
else:
    active_idx = 0

# ── sidebar: user profile switcher & status ───────────────────────────────────
with st.sidebar:
    st.markdown("## 👤 User Workspace")
    st.caption("Each user has their own private, isolated expense records.")

    selected_user_name = st.selectbox(
        "Current Active Profile",
        user_names,
        index=active_idx,
        key="profile_select",
        help="Select a profile to view and manage only their private expenses.",
    )

    # Sync selection to state & query params
    if st.session_state.get("active_user_name") != selected_user_name:
        st.session_state["active_user_name"] = selected_user_name
        st.session_state["summary"] = None  # Reset cached AI summary when user changes
        st.query_params["u"] = selected_user_name

    active_user = db.get_or_create_user(selected_user_name)
    user_id = active_user["id"]

    # Quick create profile expander
    with st.expander("➕ Create New User Profile"):
        with st.form("create_profile_form", clear_on_submit=True):
            new_profile_name = st.text_input(
                "Profile Name",
                placeholder="e.g. Alice, Work, Personal",
            )
            created_submitted = st.form_submit_button("Create & Switch", type="primary")

        if created_submitted:
            clean_name = new_profile_name.strip()
            if not clean_name:
                st.warning("Please enter a profile name.")
            else:
                new_u = db.get_or_create_user(clean_name)
                st.session_state["active_user_name"] = new_u["username"]
                st.session_state["summary"] = None
                st.query_params["u"] = new_u["username"]
                st.toast(f"Switched to profile: {clean_name} ✅")
                st.rerun()

    st.divider()
    expense_count = db.get_expense_count(user_id)
    st.metric("Expenses Logged", expense_count)
    st.divider()

    if not ai.ai_available():
        st.warning(
            "⚠️ No Groq API key found.\n\n"
            "AI features are running on keyword fallback.\n"
            "Add `GROQ_API_KEY` to your `.env` file or Streamlit Secrets.",
            icon="🤖",
        )

# ── utilities ─────────────────────────────────────────────────────────────────

def money(value: float) -> str:
    return f"{CURRENCY}{value:,.0f}"


def show_errors(errors: list[str]) -> None:
    for e in errors:
        st.error(e)


# ── load active user's expenses (strictly isolated by user_id) ────────────────
st.title("💰 AI Expense Tracker")
st.caption(f"Currently managing workspace for: **{active_user['username']}** (ID: #{user_id})")

df = db.get_all_expenses(user_id)

tab_dash, tab_add, tab_manage, tab_ai = st.tabs(
    ["📊 Dashboard", "➕ Add Expense", "🗂️ Manage", "🤖 AI Insights"]
)

# ═══════════════════════════════════════════════════════════════ Dashboard ════
with tab_dash:
    if df.empty:
        st.info(
            f"👋 No expenses yet for **{active_user['username']}**! "
            "Head over to **➕ Add Expense** to record your first one."
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
        "amount":      0.0,
        "description": "",
        "category":    "Food & Dining",
        "date":        date.today(),
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
                st.toast(f"Saved {money(amount)} under {category} for {active_user['username']} ✅")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save the expense: {exc}")

# ══════════════════════════════════════════════════════════════════ Manage ════
with tab_manage:
    if df.empty:
        st.info(f"Nothing to manage yet for **{active_user['username']}** — add some expenses first.")
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
        chosen = st.selectbox(
            "Pick an expense to edit / delete",
            list(labels),
            format_func=labels.get,
        )
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
    st.subheader(f"🤖 Spending Coach for {active_user['username']}")
    st.caption(
        "Only totals and the 5 largest expenses of the current user are sent to the AI — "
        "your private transaction data is completely isolated."
    )
    if df.empty:
        st.info(f"Add some expenses for **{active_user['username']}** first to unlock AI insights.")
    else:
        if st.button("✨ Generate summary & saving tips", type="primary"):
            with st.spinner("Analysing your spending…"):
                st.session_state.summary = ai.generate_summary(df, CURRENCY)
        if st.session_state.summary:
            st.markdown(st.session_state.summary)
