from fastapi import APIRouter
from app.api.routes import auth, accounts, transactions, dashboard

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(accounts.router)
api_router.include_router(transactions.router)
api_router.include_router(dashboard.router)
