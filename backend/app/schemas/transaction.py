from decimal import Decimal
from datetime import date, datetime
from pydantic import BaseModel
from typing import Optional


class TransactionResponse(BaseModel):
    id: str
    account_id: str
    amount: Decimal
    description: str
    category: str
    merchant: Optional[str]
    transaction_date: date
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int
    page: int
    page_size: int


class SpendingByCategoryResponse(BaseModel):
    category: str
    total: Decimal
    count: int


class DashboardResponse(BaseModel):
    total_balance: Decimal
    monthly_spending: Decimal
    monthly_income: Decimal
    spending_by_category: list[SpendingByCategoryResponse]
    recent_transactions: list[TransactionResponse]
