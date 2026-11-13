"""LLM features: parse natural language, categorize, and summarize.
If the API is unavailable, simple keyword rules keep the app working."""
import json
import re
from datetime import date, timedelta

from groq import Groq

from config import CATEGORIES, MAX_AMOUNT, MODEL, get_api_key

# ---------- Offline fallback rules (used when the API fails) ----------
KEYWORDS = {
    "Food & Dining": ["lunch", "dinner", "breakfast", "snack", "cafe", "coffee", "tea",
                      "pizza", "burger", "restaurant", "swiggy", "zomato", "biryani"],
    "Transport": ["uber", "ola", "auto", "taxi", "bus", "metro", "petrol", "fuel", "train", "cab"],
    "Groceries": ["grocery", "groceries", "vegetables", "fruits", "milk", "bigbasket", "blinkit"],
    "Shopping": ["amazon", "flipkart", "clothes", "shoes", "shirt", "shopping"],
    "Bills & Utilities": ["electricity", "wifi", "internet", "recharge", "rent", "bill", "water"],
    "Entertainment": ["movie", "netflix", "spotify", "game", "concert"],
    "Health": ["doctor", "medicine", "pharmacy", "hospital", "gym"],
    "Education": ["book", "course", "tuition", "exam", "udemy", "fees"],
    "Travel": ["flight", "hotel", "trip", "ticket", "booking"],
}


def _keyword_category(text):
    text = text.lower()
    for category, words in KEYWORDS.items():
        if any(w in text for w in words):
            return category
    return "Other"


def _fallback_parse(text):
    """Very simple regex parser: finds the first number and guesses the rest."""
    match = re.search(r"(\d[\d,]*\.?\d*)", text)
    amount = float(match.group(1).replace(",", "")) if match else 0.0
    expense_date = date.today()
    if "yesterday" in text.lower():
        expense_date -= timedelta(days=1)
    return {
        "amount": amount,
        "description": text.strip()[:200],
        "category": _keyword_category(text),
        "date": expense_date,
    }


# ---------- LLM plumbing ----------
def _ask(prompt, max_tokens=600):
    """Send one prompt to Groq and return the text reply."""
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("No API key configured")
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def _extract_json(raw):
    """Pull the first {...} block out of the reply and parse it."""
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON found in reply")
    return json.loads(raw[start:end + 1])


def ai_available():
    return bool(get_api_key())


# ---------- Public functions ----------
def parse_expense(text):
    """Turn 'Spent ₹250 on lunch yesterday' into a clean dict.
    Returns keys: amount, description, category, date, source ('ai'|'fallback')."""
    text = text.strip()[:300]
    prompt = f"""Extract an expense from the text below. Today's date is {date.today().isoformat()}.
Reply with ONLY a JSON object, no other text, with these keys:
"amount" (number, no currency symbol), "description" (short, max 8 words),
"category" (exactly one of: {", ".join(CATEGORIES)}),
"date" (YYYY-MM-DD; use today if no date is mentioned).

Text: \"\"\"{text}\"\"\""""
    try:
        data = _extract_json(_ask(prompt, max_tokens=200))
        amount = float(data["amount"])
        if not 0 < amount <= MAX_AMOUNT:
            raise ValueError("Amount out of range")
        category = data.get("category")
        if category not in CATEGORIES:
            category = _keyword_category(text)
        try:
            expense_date = date.fromisoformat(str(data.get("date")))
        except ValueError:
            expense_date = date.today()
        if expense_date > date.today():
            expense_date = date.today()
        return {
            "amount": amount,
            "description": str(data.get("description") or text)[:200],
            "category": category,
            "date": expense_date,
            "source": "ai",
        }
    except Exception:
        result = _fallback_parse(text)
        result["source"] = "fallback"
        return result


def categorize(description):
    """Suggest a category for a description typed manually."""
    prompt = (f"Pick the single best category for this expense: \"{description}\".\n"
              f"Options: {', '.join(CATEGORIES)}.\nReply with only the category name.")
    try:
        answer = _ask(prompt, max_tokens=20).strip().strip(".")
        if answer in CATEGORIES:
            return answer
    except Exception:
        pass
    return _keyword_category(description)


def generate_summary(df, currency="₹"):
    """Create a spending summary + saving tips from aggregated data.
    Only totals are sent to the API, not every raw record."""
    if df.empty:
        return "Add some expenses first and I'll analyse them."
    by_cat = df.groupby("category")["amount"].sum().sort_values(ascending=False).round(2)
    by_month = df.groupby("month")["amount"].sum().round(2)
    biggest = df.nlargest(5, "amount")[["expense_date", "description", "amount"]]
    biggest_text = "\n".join(
        f"- {r.expense_date:%Y-%m-%d} {r.description}: {r.amount:.0f}" for r in biggest.itertuples()
    )
    prompt = f"""You are a friendly personal-finance coach. Currency is {currency}.
Total spent: {df['amount'].sum():.0f} across {len(df)} expenses.
Spending by category:\n{by_cat.to_string()}
Spending by month:\n{by_month.to_string()}
Five biggest expenses:\n{biggest_text}

Write in Markdown, under 250 words:
1. **Summary** (2-3 sentences)
2. **Key observations** (3 bullets, reference real numbers)
3. **Saving suggestions** (3-4 specific, practical bullets)
Be encouraging, not judgmental."""
    try:
        return _ask(prompt, max_tokens=700)
    except Exception:
        top = by_cat.index[0]
        return (f"⚠️ AI summary unavailable, here is a quick overview.\n\n"
                f"- Total spent: **{currency}{df['amount'].sum():,.0f}**\n"
                f"- Biggest category: **{top}** ({currency}{by_cat.iloc[0]:,.0f})\n"
                f"- Tip: review your top category for easy savings.")
