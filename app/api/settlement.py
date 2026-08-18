"""知识沉淀与 FAQ 接口：/api/settlement/*。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import KnowledgeGap
from app.schemas.schemas import FaqReviewRequest, GapResolveRequest
from app.services.faq_service import faq_service

router = APIRouter()


@router.get("/faqs/recommendations")
def list_faq_recommendations(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取高频问题挖掘推荐列表。"""
    return faq_service.mine_faq_recommendations(db)


@router.post("/faqs/{faq_id}/review")
def review_faq(faq_id: int, payload: FaqReviewRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """审核 FAQ（approve / reject）。"""
    return faq_service.review_faq(db, faq_id, payload.action, payload.edited_answer, int(user["user_id"]))


@router.get("/faqs")
def list_published_faqs(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """展示已发布 FAQ 库及缓存生效状态。"""
    return faq_service.list_published_faqs(db)


@router.get("/knowledge-gaps")
def list_knowledge_gaps(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取知识缺口列表。"""
    return faq_service.identify_knowledge_gaps(db)


@router.patch("/knowledge-gaps/{gap_id}")
def resolve_knowledge_gap(gap_id: int, payload: GapResolveRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """标记知识缺口为已解决或已拒绝。"""
    gap = db.get(KnowledgeGap, gap_id)
    if not gap:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="知识缺口不存在")
    if payload.action == "resolve":
        gap.status = "resolved"
        if payload.resolved_unit_id:
            gap.resolved_unit_id = payload.resolved_unit_id
    elif payload.action == "reject":
        gap.status = "rejected"
    db.commit()
    return {"id": gap.id, "status": gap.status, "resolved_unit_id": gap.resolved_unit_id}