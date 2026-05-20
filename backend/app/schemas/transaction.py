from decimal import Decimal
from datetime import date, datetime
from pydantic import BaseModel
from typing import Optional


class TransactionCreate(BaseModel):
    account_id: str
    amount: Decimal
    description: str
    category: str
    merchant: Optional[str] = None
    transaction_date: date


class ReceiptLineItem(BaseModel):
    name: str
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    total: Optional[Decimal] = None


class ReceiptScanResponse(BaseModel):
    merchant: Optional[str] = None
    amount: Optional[Decimal] = None
    description: str = ""
    category: str = "Shopping"
    transaction_date: Optional[date] = None
    tax: Optional[Decimal] = None
    tip: Optional[Decimal] = None
    items: list[ReceiptLineItem] = []


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
