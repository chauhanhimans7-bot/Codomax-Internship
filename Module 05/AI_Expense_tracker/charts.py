"""Plotly chart builders. Each function takes a DataFrame and returns a figure."""
import plotly.express as px

from config import CURRENCY


def category_bar(df):
    data = df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    fig = px.bar(data, x="category", y="amount", text_auto=".0f",
                 labels={"amount": f"Amount ({CURRENCY})", "category": ""},
                 title="Spending by category")
    fig.update_layout(showlegend=False)
    return fig


def category_pie(df):
    data = df.groupby("category", as_index=False)["amount"].sum()
    return px.pie(data, names="category", values="amount", hole=0.4,
                  title="Share of spending by category")


def spending_trend(df, mode="Monthly"):
    """Line chart: total spending per month or per day."""
    if mode == "Monthly":
        data = df.groupby("month", as_index=False)["amount"].sum().sort_values("month")
        x = "month"
    else:
        data = (df.assign(day=df["expense_date"].dt.date)
                  .groupby("day", as_index=False)["amount"].sum().sort_values("day"))
        x = "day"
    fig = px.line(data, x=x, y="amount", markers=True,
                  labels={"amount": f"Amount ({CURRENCY})", x: ""},
                  title=f"{mode} spending trend")
    return fig
