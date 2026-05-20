from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.models.budget import Budget
from app.schemas.budget import BudgetSet, BudgetResponse
from app.dependencies import get_current_user

router = APIRouter(prefix="/budget", tags=["budget"])


@router.get("", response_model=BudgetResponse)
def get_budget(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    budget = db.query(Budget).filter(Budget.user_id == current_user.id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No budget set")
    return budget


@router.put("", response_model=BudgetResponse)
def set_budget(
    payload: BudgetSet,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    budget = db.query(Budget).filter(Budget.user_id == current_user.id).first()
    if budget:
        budget.amount = payload.amount
    else:
        budget = Budget(user_id=current_user.id, amount=payload.amount)
        db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget
