from __future__ import annotations
import json
import redis
from app.core.config import settings

_client: redis.Redis | None = None
_TTL = 60 * 60 * 24 * 7  # 7 days


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def _key(user_id: str) -> str:
    return f"chat:session:{user_id}"


def get_history(user_id: str) -> list[dict]:
    raw = _get_client().get(_key(user_id))
    return json.loads(raw) if raw else []


def append_messages(user_id: str, messages: list[dict]) -> None:
    r = _get_client()
    k = _key(user_id)
    existing = json.loads(r.get(k) or "[]")
    existing.extend(messages)
    r.set(k, json.dumps(existing), ex=_TTL)


def clear_history(user_id: str) -> None:
    _get_client().delete(_key(user_id))
