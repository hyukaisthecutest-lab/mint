from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.core.database import get_db
from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.schemas.transaction import DashboardResponse, SpendingByCategoryResponse
from app.dependencies import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today()
    month_start = today.replace(day=1)

    total_balance = db.query(func.sum(Account.balance)).filter(
        Account.user_id == current_user.id, Account.is_active
    ).scalar() or Decimal("0")

    monthly_spending = db.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date >= month_start,
        Transaction.amount < 0,
    ).scalar() or Decimal("0")

    monthly_income = db.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date >= month_start,
        Transaction.amount > 0,
    ).scalar() or Decimal("0")

    category_rows = (
        db.query(Transaction.category, func.sum(Transaction.amount).label("total"), func.count().label("count"))
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.transaction_date >= month_start,
            Transaction.amount < 0,
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount))
        .all()
    )

    spending_by_category = [
        SpendingByCategoryResponse(category=row.category, total=abs(row.total), count=row.count)
        for row in category_rows
    ]

    recent = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(desc(Transaction.transaction_date), desc(Transaction.created_at))
        .limit(10)
        .all()
    )

    return DashboardResponse(
        total_balance=total_balance,
        monthly_spending=abs(monthly_spending),
        monthly_income=monthly_income,
        spending_by_category=spending_by_category,
        recent_transactions=recent,
    )
