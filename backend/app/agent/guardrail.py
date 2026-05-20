from __future__ import annotations
from langchain_openai import ChatOpenAI
from app.core.config import settings

_model: ChatOpenAI | None = None

_SYSTEM = """You are a guardrail for a personal finance assistant.
Decide if the user's message is related to personal finance, spending, budgets, transactions, or money management.
Reply with only "PASS" or "BLOCK". Nothing else.

PASS: spending questions, budget questions, transaction questions, saving tips, cost reduction advice, financial summaries.
BLOCK: everything else (jokes, coding help, general knowledge, creative writing, etc.)."""


def _get_model() -> ChatOpenAI:
    global _model
    if _model is None:
        _model = ChatOpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY)
    return _model


def is_finance_question(message: str) -> bool:
    response = _get_model().invoke([
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": message},
    ])
    return response.content.strip().upper() == "PASS"
