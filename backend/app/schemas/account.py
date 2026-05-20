from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class LinkAccountRequest(BaseModel):
    name: str
    institution: str
    account_type: str  # checking, savings, credit
    initial_balance: Decimal = Decimal("0")


class AccountResponse(BaseModel):
    id: str
    name: str
    institution: str
    account_type: str
    balance: Decimal
    external_account_id: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SyncResponse(BaseModel):
    task_id: str
    message: str
