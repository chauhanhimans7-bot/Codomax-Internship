# 💰 AI Expense Tracker (Secure Multi-User)

Streamlit + Pandas + SQLite + Plotly + Groq API.

## Features
- 🔐 **Multi-User Authentication**: Sign In & Sign Up with secure PBKDF2 password hashing + per-user salt.
- 🛡️ **Complete Data Isolation**: Each user can only view, create, edit, delete, and analyze their own expenses.
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
| `app.py` | Streamlit multi-user dashboard and main UI |
| `auth.py` | Authentication UI (Login / Register) and session management |
| `database.py` | SQLite schema, secure password hashing, and user-isolated CRUD |
| `ai_helper.py` | LLM parsing, categorization, and spending summaries (+ fallback rules) |
| `charts.py` | Plotly bar, pie, and trend charts |
| `config.py` | Central configuration, category lists, and environment loader |

## API Key & Security
- Groq API key is stored securely in `.env` (git-ignored) or `.streamlit/secrets.toml`.
- Passwords are encrypted using salted PBKDF2-HMAC-SHA256 (310,000 iterations).
- Backend and database queries strictly scope all records by authenticated `user_id`.
