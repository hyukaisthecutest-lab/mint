from fastapi import APIRouter
from app.api.routes import auth, accounts, transactions, dashboard, budget, chat, agent_status

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(accounts.router)
api_router.include_router(transactions.router)
api_router.include_router(dashboard.router)
api_router.include_router(budget.router)
api_router.include_router(chat.router)
api_router.include_router(agent_status.router)
