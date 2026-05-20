from __future__ import annotations
import calendar
from datetime import date
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.transaction import Transaction
from app.models.budget import Budget


def _month_range(month: str) -> tuple[date, date]:
    year, mon = map(int, month.split("-"))
    start = date(year, mon, 1)
    end = date(year, mon, calendar.monthrange(year, mon)[1])
    return start, end


def _prev_months(n: int) -> list[tuple[date, date, str]]:
    today = date.today()
    year, month = today.year, today.month
    result = []
    for _ in range(n):
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])
        label = start.strftime("%B %Y")
        result.insert(0, (start, end, label))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return result


def make_tools(user_id: str, db: Session) -> list:
    @tool
    def get_spending_by_category(month: str) -> str:
        """Get spending broken down by category for a given month. month format: YYYY-MM (e.g. 2026-05)"""
        try:
            start, end = _month_range(month)
        except Exception:
            return "Invalid month format. Use YYYY-MM."

        rows = (
            db.query(Transaction.category, func.sum(Transaction.amount).label("total"))
            .filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
                Transaction.amount < 0,
            )
            .group_by(Transaction.category)
            .order_by(func.sum(Transaction.amount))
            .all()
        )

        if not rows:
            return f"No spending found for {month}."

        total = sum(abs(float(r.total)) for r in rows)
        lines = [f"Spending by category for {month}:"]
        for r in rows:
            amt = abs(float(r.total))
            pct = amt / total * 100
            lines.append(f"  {r.category}: ${amt:,.2f} ({pct:.1f}%)")
        lines.append(f"  Total: ${total:,.2f}")
        return "\n".join(lines)

    @tool
    def get_spending_trend(months: int = 3) -> str:
        """Get monthly spending totals for the last N months to show trends. months: number of months to look back."""
        periods = _prev_months(months)
        lines = [f"Monthly spending trend (last {months} months):"]
        for start, end, label in periods:
            total = db.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
                Transaction.amount < 0,
            ).scalar() or 0
            lines.append(f"  {label}: ${abs(float(total)):,.2f}")
        return "\n".join(lines)

    @tool
    def get_top_merchants(month: str, limit: int = 5) -> str:
        """Get top merchants by spending for a given month. month format: YYYY-MM"""
        try:
            start, end = _month_range(month)
        except Exception:
            return "Invalid month format. Use YYYY-MM."

        rows = (
            db.query(Transaction.merchant, func.sum(Transaction.amount).label("total"))
            .filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
                Transaction.amount < 0,
                Transaction.merchant.isnot(None),
            )
            .group_by(Transaction.merchant)
            .order_by(func.sum(Transaction.amount))
            .limit(limit)
            .all()
        )

        if not rows:
            return f"No merchant data found for {month}."

        lines = [f"Top {limit} merchants for {month}:"]
        for r in rows:
            lines.append(f"  {r.merchant}: ${abs(float(r.total)):,.2f}")
        return "\n".join(lines)

    @tool
    def get_budget_status() -> str:
        """Get current budget vs actual spending for this month."""
        budget = db.query(Budget).filter(Budget.user_id == user_id).first()
        if not budget:
            return "No budget has been set."

        today = date.today()
        start = date(today.year, today.month, 1)
        spent = abs(
            db.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.amount < 0,
            ).scalar() or 0
        )

        budget_amt = float(budget.amount)
        remaining = budget_amt - float(spent)
        pct = float(spent) / budget_amt * 100 if budget_amt > 0 else 0
        status = "OVER BUDGET" if remaining < 0 else "on track"
        return (
            f"Budget status for {today.strftime('%B %Y')} ({status}):\n"
            f"  Budget: ${budget_amt:,.2f}\n"
            f"  Spent:  ${float(spent):,.2f} ({pct:.1f}%)\n"
            f"  Remaining: ${remaining:,.2f}"
        )

    @tool
    def get_transactions(category: str, month: str) -> str:
        """Get individual transactions for a specific category and month. month format: YYYY-MM"""
        try:
            start, end = _month_range(month)
        except Exception:
            return "Invalid month format. Use YYYY-MM."

        rows = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
                Transaction.category.ilike(f"%{category}%"),
                Transaction.amount < 0,
            )
            .order_by(Transaction.transaction_date.desc())
            .limit(10)
            .all()
        )

        if not rows:
            return f"No {category} transactions found for {month}."

        lines = [f"{category} transactions for {month}:"]
        for r in rows:
            lines.append(f"  {r.transaction_date} | {r.description}: ${abs(float(r.amount)):,.2f}")
        return "\n".join(lines)

    return [
        get_spending_by_category,
        get_spending_trend,
        get_top_merchants,
        get_budget_status,
        get_transactions,
    ]
