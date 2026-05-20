from datetime import datetime, timezone
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.budget import Budget
from app.models.transaction import Transaction
from app.models.user import User
from app.services.email import send_budget_warning, send_budget_exceeded
from sqlalchemy import func


@celery_app.task(name="check_budgets")
def check_budgets():
    db = SessionLocal()
    try:
        today = datetime.now(timezone.utc)
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        budgets = db.query(Budget).all()
        for budget in budgets:
            user = db.query(User).filter(User.id == budget.user_id).first()
            if not user:
                continue

            spent = abs(
                db.query(func.sum(Transaction.amount))
                .filter(
                    Transaction.user_id == budget.user_id,
                    Transaction.transaction_date >= month_start.date(),
                    Transaction.amount < 0,
                )
                .scalar() or 0
            )

            budget_amount = float(budget.amount)
            pct = spent / budget_amount if budget_amount > 0 else 0

            already_warned_this_month = (
                budget.warned_at and budget.warned_at >= month_start
            )
            already_exceeded_this_month = (
                budget.exceeded_at and budget.exceeded_at >= month_start
            )

            if pct >= 1.0 and not already_exceeded_this_month:
                send_budget_exceeded(user.email, spent, budget_amount)
                budget.exceeded_at = today

            elif pct >= 0.8 and not already_warned_this_month:
                send_budget_warning(user.email, spent, budget_amount)
                budget.warned_at = today

        db.commit()
    finally:
        db.close()
