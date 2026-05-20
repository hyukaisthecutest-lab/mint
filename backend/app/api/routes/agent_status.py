from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.dependencies import require_admin
from app.models.user import User
from app.core.metrics_store import store

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/status")
def status(current_user: User = Depends(require_admin)):
    return store.snapshot()


@router.get("/status/stream")
async def status_stream(current_user: User = Depends(require_admin)):
    async def generate():
        try:
            while True:
                data = store.snapshot()
                yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(3)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
