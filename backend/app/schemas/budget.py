from decimal import Decimal
from pydantic import BaseModel


class BudgetSet(BaseModel):
    amount: Decimal


class BudgetResponse(BaseModel):
    amount: Decimal

    class Config:
        from_attributes = True
