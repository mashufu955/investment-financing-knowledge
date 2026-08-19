"""AI 检索与问答鉴权接口：/api/ai/*。"""
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.schemas import ChatStreamRequest
from app.services.ai_qa_service import ai_qa_service

router = APIRouter()


@router.post("/chat/stream")
def chat_stream(payload: ChatStreamRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """SSE 流式问答。"""
    user_id = int(user["user_id"])

    async def event_source() -> AsyncIterator[bytes]:
        async for event in ai_qa_service.chat_stream(db, user_id, payload.question, payload.session_id):
            line = f"event: {event['event']}\ndata: {event['data']}\n\n"
            yield line.encode("utf-8")

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.get("/sessions")
def list_history_sessions(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取历史对话会话列表。"""
    return ai_qa_service.list_history_sessions(db, int(user["user_id"]))


@router.get("/sessions/{session_id}/messages")
def list_session_messages(session_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取指定会话的消息列表（校验会话归属，防止越权读取他人会话）。"""
    from sqlalchemy import select

    from app.models.models import QaMessage, QaSession

    session = db.execute(
        select(QaSession).where(
            QaSession.session_id == session_id, QaSession.user_id == int(user["user_id"])
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    rows = db.execute(
        select(QaMessage).where(QaMessage.session_id == session_id).order_by(QaMessage.created_at)
    ).scalars()
    return [{"role": m.role, "content": m.content} for m in rows]