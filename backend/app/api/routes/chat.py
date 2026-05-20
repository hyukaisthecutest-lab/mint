from __future__ import annotations
import base64
import io
import logging
import time
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage
from openai import OpenAI, RateLimitError, APITimeoutError
from opentelemetry import trace
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from celery.result import AsyncResult
from app.core.database import get_db
from app.core.config import settings
from app.core.telemetry import tracer, agent_requests, agent_errors, agent_duration
from app.core.metrics_store import store
from app.core.session_store import get_history, append_messages, clear_history
from app.core.celery_app import celery_app
from app.models.user import User
from app.models.chat_log import ChatLog
from app.dependencies import get_current_user
from app.agent.graph import create_graph
from app.tasks.chat_tasks import process_chat

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("mint.chat")
_openai: OpenAI | None = None


def _get_openai() -> OpenAI:
    global _openai
    if _openai is None:
        _openai = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai

_RETRY = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class ChatRequest(BaseModel):
    message: str
    voice_mode: bool = False


@retry(**_RETRY)
def _invoke_agent(user_id: str, db: Session, messages: list) -> tuple[str, int, int]:
    from app.agent.observer import AgentObserver
    observer = AgentObserver()
    graph = create_graph(user_id, db, observer=observer)
    result = graph.invoke({"messages": messages})
    return result["messages"][-1].content, observer.total_prompt_tokens, observer.total_completion_tokens


@retry(**_RETRY)
def _tts(text: str) -> str:
    tts = _get_openai().audio.speech.create(model="tts-1", voice="nova", input=text)
    return base64.b64encode(tts.read()).decode()


@router.get("/history")
def history(current_user: User = Depends(get_current_user)):
    return {"history": get_history(str(current_user.id))}


@router.delete("/history")
def delete_history(current_user: User = Depends(get_current_user)):
    clear_history(str(current_user.id))
    return {"ok": True}


@router.post("")
def chat(
    request: Request,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trace_id = request.headers.get("X-Trace-ID", "none")
    t0 = time.perf_counter()
    user_id = str(current_user.id)

    store.request_start(user_id=user_id, message=payload.message)
    agent_requests.labels(voice_mode=str(payload.voice_mode)).inc()

    session = get_history(user_id)
    logger.info("chat_request", extra={"extra": {
        "trace_id": trace_id,
        "user_id": user_id,
        "voice_mode": payload.voice_mode,
        "message_preview": payload.message[:100],
        "history_len": len(session),
    }})

    with tracer.start_as_current_span("chat.request") as span:
        span.set_attribute("trace_id", trace_id)
        span.set_attribute("user_id", user_id)
        span.set_attribute("voice_mode", payload.voice_mode)
        span.set_attribute("message", payload.message[:200])

        messages = []
        for msg in session:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=payload.message))

        try:
            answer, prompt_tokens, completion_tokens = _invoke_agent(user_id, db, messages)
        except RateLimitError:
            messages_data = [*session, {"role": "user", "content": payload.message}]
            task = process_chat.delay(user_id, messages_data, payload.voice_mode, payload.message)
            elapsed_err = (time.perf_counter() - t0) * 1000
            store.request_end(latency_ms=elapsed_err, user_id=user_id)
            logger.warning("chat_rate_limited_queued", extra={"extra": {
                "trace_id": trace_id, "user_id": user_id, "job_id": task.id,
            }})
            return JSONResponse(status_code=202, content={
                "queued": True,
                "job_id": task.id,
                "trace_id": trace_id,
            })
        except Exception as e:
            agent_errors.labels(step="agent").inc()
            elapsed_err = (time.perf_counter() - t0) * 1000
            store.request_end(latency_ms=elapsed_err, error=True, user_id=user_id)
            span.set_status(trace.StatusCode.ERROR, str(e))
            logger.error("chat_agent_error", extra={"extra": {
                "trace_id": trace_id, "user_id": user_id, "error": str(e),
            }})
            db.add(ChatLog(
                user_id=user_id, trace_id=trace_id, message=payload.message,
                voice_mode=payload.voice_mode, latency_ms=round(elapsed_err, 2),
                prompt_tokens=0, completion_tokens=0, error=True,
            ))
            db.commit()
            raise HTTPException(status_code=500, detail="Agent failed to respond. Please try again.")

        append_messages(user_id, [
            {"role": "user", "content": payload.message},
            {"role": "assistant", "content": answer},
        ])

        elapsed_ms = (time.perf_counter() - t0) * 1000
        db.add(ChatLog(
            user_id=user_id, trace_id=trace_id, message=payload.message,
            response=answer, voice_mode=payload.voice_mode,
            latency_ms=round(elapsed_ms, 2),
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            error=False,
        ))
        db.commit()

        audio_b64: str | None = None
        if payload.voice_mode:
            tts_t0 = time.perf_counter()
            try:
                audio_b64 = _tts(answer)
                agent_duration.labels(step="tts").observe(time.perf_counter() - tts_t0)
            except Exception as e:
                agent_errors.labels(step="tts").inc()
                logger.warning("tts_error", extra={"extra": {"trace_id": trace_id, "error": str(e)}})

        elapsed = time.perf_counter() - t0
        agent_duration.labels(step="total").observe(elapsed)
        store.request_end(latency_ms=elapsed * 1000, user_id=user_id)
        span.set_attribute("elapsed_s", round(elapsed, 3))

        logger.info("chat_response", extra={"extra": {
            "trace_id": trace_id,
            "user_id": user_id,
            "elapsed_s": round(elapsed, 3),
            "has_audio": audio_b64 is not None,
        }})

    return {"text": answer, "audio": audio_b64, "trace_id": trace_id, "elapsed_ms": round(elapsed * 1000)}


@router.get("/status/{job_id}")
def chat_status(job_id: str, current_user: User = Depends(get_current_user)):
    result = AsyncResult(job_id, app=celery_app)
    if result.state in ("PENDING", "STARTED", "RETRY"):
        return {"status": "pending"}
    if result.state == "SUCCESS":
        data = result.result or {}
        if data.get("error"):
            return {"status": "error", "error": data["error"]}
        return {"status": "done", "text": data["text"], "audio": None}
    if result.state == "FAILURE":
        return {"status": "error", "error": str(result.result)}
    return {"status": "pending"}


@retry(**_RETRY)
def _transcribe(buf: io.BytesIO) -> str:
    buf.seek(0)
    return _get_openai().audio.transcriptions.create(model="whisper-1", file=buf).text


@router.post("/transcribe")
async def transcribe(
    request: Request,
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    trace_id = request.headers.get("X-Trace-ID", "none")
    t0 = time.perf_counter()
    audio_bytes = await audio.read()
    buf = io.BytesIO(audio_bytes)
    buf.name = "recording.webm"

    with tracer.start_as_current_span("chat.transcribe") as span:
        span.set_attribute("trace_id", trace_id)
        try:
            text = _transcribe(buf)
            agent_duration.labels(step="transcribe").observe(time.perf_counter() - t0)
        except Exception as e:
            agent_errors.labels(step="transcribe").inc()
            span.set_status(trace.StatusCode.ERROR, str(e))
            logger.error("transcribe_error", extra={"extra": {"trace_id": trace_id, "error": str(e)}})
            raise HTTPException(status_code=500, detail="Transcription failed. Please try again.")

    logger.info("transcribe_done", extra={"extra": {
        "trace_id": trace_id,
        "elapsed_s": round(time.perf_counter() - t0, 3),
        "text_preview": text[:80],
    }})
    return {"text": text}
