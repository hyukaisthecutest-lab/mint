from __future__ import annotations
import base64
import io
import logging
import time
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage
from openai import OpenAI, RateLimitError, APITimeoutError
from opentelemetry import trace
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from app.core.database import get_db
from app.core.config import settings
from app.core.telemetry import tracer, agent_requests, agent_errors, agent_duration
from app.core.metrics_store import store
from app.models.user import User
from app.dependencies import get_current_user
from app.agent.graph import create_graph

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("mint.chat")
_openai = OpenAI(api_key=settings.OPENAI_API_KEY)

_RETRY = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    voice_mode: bool = False


@retry(**_RETRY)
def _invoke_agent(user_id: str, db: Session, messages: list) -> str:
    graph = create_graph(user_id, db)
    result = graph.invoke({"messages": messages})
    return result["messages"][-1].content


@retry(**_RETRY)
def _tts(text: str) -> str:
    tts = _openai.audio.speech.create(model="tts-1", voice="nova", input=text)
    return base64.b64encode(tts.read()).decode()


@router.post("")
def chat(
    request: Request,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trace_id = request.headers.get("X-Trace-ID", "none")
    t0 = time.perf_counter()

    store.request_start()
    agent_requests.labels(voice_mode=str(payload.voice_mode)).inc()
    logger.info("chat_request", extra={"extra": {
        "trace_id": trace_id,
        "user_id": current_user.id,
        "voice_mode": payload.voice_mode,
        "message_preview": payload.message[:100],
        "history_len": len(payload.history),
    }})

    with tracer.start_as_current_span("chat.request") as span:
        span.set_attribute("trace_id", trace_id)
        span.set_attribute("user_id", current_user.id)
        span.set_attribute("voice_mode", payload.voice_mode)
        span.set_attribute("message", payload.message[:200])

        messages = []
        for msg in payload.history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        messages.append(HumanMessage(content=payload.message))

        try:
            answer = _invoke_agent(current_user.id, db, messages)
        except Exception as e:
            agent_errors.labels(step="agent").inc()
            store.request_end(latency_ms=(time.perf_counter() - t0) * 1000, error=True)
            span.set_status(trace.StatusCode.ERROR, str(e))
            logger.error("chat_agent_error", extra={"extra": {
                "trace_id": trace_id, "user_id": current_user.id, "error": str(e),
            }})
            raise HTTPException(status_code=500, detail="Agent failed to respond. Please try again.")

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
        store.request_end(latency_ms=elapsed * 1000)
        span.set_attribute("elapsed_s", round(elapsed, 3))

        logger.info("chat_response", extra={"extra": {
            "trace_id": trace_id,
            "user_id": current_user.id,
            "elapsed_s": round(elapsed, 3),
            "has_audio": audio_b64 is not None,
        }})

    return {"text": answer, "audio": audio_b64, "trace_id": trace_id, "elapsed_ms": round(elapsed * 1000)}


@retry(**_RETRY)
def _transcribe(buf: io.BytesIO) -> str:
    buf.seek(0)
    return _openai.audio.transcriptions.create(model="whisper-1", file=buf).text


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
