"""Central settings: categories, DB path, and secure API key loading."""
        
        
from pathlib import Path
import streamlit as st
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Reads the project ".env" file into environment variables.
load_dotenv(BASE_DIR / ".env")

DB_PATH = str(BASE_DIR / "expenses.db")
CURRENCY = "₹"
MAX_AMOUNT = 10_000_000          # sanity limit for a single expense
MAX_DESC_LENGTH = 200
MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")

CATEGORIES = [
    "Food & Dining",
    "Transport",
    "Shopping",
    "Bills & Utilities",
    "Entertainment",
    "Health",
    "Education",
    "Travel",
    "Groceries",
    "Other",
]


def get_api_key():
    """Return the Groq API key from env/.env first, then Streamlit secrets.
    The key is never hard-coded and never shown in the UI."""
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    try:
        return st.secrets.get("GROQ_API_KEY")   # .streamlit/secrets.toml
    except Exception:
        return None
