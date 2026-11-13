# 💰 AI Expense Tracker (Multi-User Isolated Workspaces)

Streamlit + Pandas + SQLite + Plotly + Groq API.

## Features
- 🚀 **Instant Access**: Zero login walls or password hurdles — launches directly into the dashboard.
- 🛡️ **Complete Data Isolation**: Each user/profile has their own private workspace. Users can only view, add, update, delete, and analyze their own expenses.
- 👤 **Profile Switching & Bookmarking**: Easily switch or create new profiles in the sidebar; preserve your active workspace with direct URLs (`?u=YourName`).
- 🤖 **AI-Powered Insights**: Fast expense categorization, natural language expense parsing, and spending summaries powered by Groq (`qwen/qwen3.8-27b`).
- 📊 **Interactive Analytics**: Real-time spending charts and category breakdowns.

## Setup
```bash
python -m venv venv
venv\Scripts\activate            # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Files
| File | Purpose |
|---|---|
| `app.py` | Streamlit dashboard, profile switcher, and main UI |
| `database.py` | SQLite schema, profile management, and user-isolated CRUD |
| `ai_helper.py` | LLM parsing, categorization, and spending summaries (+ fallback rules) |
| `charts.py` | Plotly bar, pie, and trend charts |
| `config.py` | Central configuration, category lists, and environment loader |

## Data Isolation & Security
- Backend and database queries strictly scope all records by `user_id`.
- Groq API key is stored securely in `.env` (git-ignored) or `.streamlit/secrets.toml`.
