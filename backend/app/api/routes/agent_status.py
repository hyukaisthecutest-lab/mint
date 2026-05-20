from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from app.dependencies import require_admin
from app.models.user import User
from app.core.database import get_db
from app.core.security import decode_token
from app.core.metrics_store import store

router = APIRouter(prefix="/agent", tags=["agent"])


def _get_admin_from_token(token: str, db: Session) -> User:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


@router.get("/status")
def status_snapshot(current_user: User = Depends(require_admin)):
    return store.snapshot()


@router.websocket("/status/ws")
async def status_ws(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        _get_admin_from_token(token, db)
    except HTTPException as e:
        await websocket.close(code=4403, reason=e.detail)
        return

    await websocket.accept()
    try:
        while True:
            data = store.snapshot()
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(3)
    except (WebSocketDisconnect, Exception):
        pass
