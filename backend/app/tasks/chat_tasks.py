from __future__ import annotations
import logging
from celery import Task
from openai import RateLimitError
from app.core.celery_app import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger("mint.chat_tasks")

_DEFAULT_RETRY_COUNTDOWN = 60  # seconds; overridden by Retry-After header when present


def _retry_countdown(exc: RateLimitError) -> int:
    try:
        retry_after = exc.response.headers.get("retry-after")
        if retry_after:
            return int(retry_after) + 5
    except Exception:
        pass
    return _DEFAULT_RETRY_COUNTDOWN


@celery_app.task(
    bind=True,
    name="process_chat",
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_chat(
    self: Task,
    user_id: str,
    messages_data: list[dict],
    voice_mode: bool,
    new_user_message: str,
) -> dict:
    from langchain_core.messages import HumanMessage, AIMessage
    from app.agent.graph import create_graph
    from app.agent.observer import AgentObserver
    from app.core.session_store import append_messages

    messages = []
    for m in messages_data:
        if m["role"] == "user":
            messages.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            messages.append(AIMessage(content=m["content"]))

    db = SessionLocal()
    try:
        observer = AgentObserver()
        graph = create_graph(user_id, db, observer=observer)
        result = graph.invoke({"messages": messages})
        answer = result["messages"][-1].content

        append_messages(user_id, [
            {"role": "user", "content": new_user_message},
            {"role": "assistant", "content": answer},
        ])

        return {"text": answer, "error": None}
    except RateLimitError as exc:
        countdown = _retry_countdown(exc)
        logger.warning(
            "rate_limit_retry",
            extra={"countdown": countdown, "attempt": self.request.retries},
        )
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        logger.error("chat_task_error", extra={"error": str(exc)})
        return {"text": None, "error": str(exc)}
    finally:
        db.close()
