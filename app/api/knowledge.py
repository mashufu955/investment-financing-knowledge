"""投融资知识维护接口：/api/knowledge/*。"""
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BeforeValidator
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.schemas import (
    CheckPermissionsRequest,
    CheckPermissionsResponse,
    ConfigureUnitPermissionsRequest,
    ImportResponse,
    UnitCreateRequest,
    UnitDetail,
    UnitListItem,
    UnitUpdateRequest,
)
from app.services.knowledge_service import knowledge_service
from app.services.permission_service import permission_service

router = APIRouter()


def _blank_to_none(v):
    """兼容前端传空字符串的整型参数：'' 视为未传，否则 FastAPI 校验失败返回 422。"""
    return None if v == "" else v


# 保密级别：int | None，且容忍空串
ConfidentialLevel = Annotated[int | None, BeforeValidator(_blank_to_none)]


@router.post("/import", response_model=ImportResponse)
def import_documents(
    files: list[UploadFile],
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """单文件/多文件批量上传，导入项目尽调、投研报告、投决材料、协议与投后报告。
    声明为同步函数（def 而非 async def），由 FastAPI 在线程池中执行，
    避免模型加载与向量化阻塞事件循环。"""
    return knowledge_service.import_documents(db, files, int(user["user_id"]))


@router.post("/units", response_model=UnitListItem)
def create_unit(payload: UnitCreateRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """新建投融资知识单元（缺口补全等场景）。"""
    return knowledge_service.create_unit(db, payload.model_dump(), int(user["user_id"]))


@router.get("/import/{task_id}")
def poll_import_progress(task_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """轮询导入任务进度：返回后台任务状态 + 已创建知识单元列表。"""
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from app.models.models import KnowledgeUnit

    task_info = knowledge_service.get_import_status(task_id)
    # 按创建者 + 最近创建时间关联导入单元（unit_code 为 YYYYMMDDNNNN，不含 task_id）
    uid = int(user["user_id"])
    since = datetime.utcnow() - timedelta(hours=1)
    rows = db.execute(
        select(KnowledgeUnit).where(
            KnowledgeUnit.creator_id == uid,
            KnowledgeUnit.created_at >= since,
        ).order_by(KnowledgeUnit.created_at.desc())
    ).scalars()
    items = [
        {"unit_code": r.unit_code, "status": r.status, "title": r.title, "version": r.version}
        for r in rows
    ]
    return {
        "task_id": task_id,
        "status": task_info.get("status", "unknown"),
        "total_files": task_info.get("total_files", 0),
        "processed_files": task_info.get("processed_files", 0),
        "error": task_info.get("error"),
        "items": items,
    }


@router.get("/units")
def list_units(
    industry: str | None = None,
    financing_round: str | None = None,
    deal_stage: str | None = None,
    confidential_level: ConfidentialLevel = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按行业、轮次、项目阶段、保密级别、状态分页查询知识单元。"""
    return knowledge_service.list_units(
        db,
        {
            "industry": industry,
            "financing_round": financing_round,
            "deal_stage": deal_stage,
            "confidential_level": confidential_level,
            "status": status,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/units/{unit_id}", response_model=UnitDetail)
def get_unit(unit_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询知识单元详情与已配置的数据权限列表。"""
    return knowledge_service.get_unit(db, unit_id)


@router.put("/units/{unit_id}", response_model=UnitListItem)
def update_unit(unit_id: int, payload: UnitUpdateRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新知识单元内容。"""
    return knowledge_service.update_unit(db, unit_id, payload.model_dump(), int(user["user_id"]))


@router.delete("/units")
def delete_units(unit_ids: list[int], user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """批量删除知识单元。"""
    count = knowledge_service.delete_units(db, unit_ids)
    return {"deleted": count}


@router.post("/units/{unit_id}/permissions")
def configure_unit_permissions(unit_id: int, payload: ConfigureUnitPermissionsRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """批量配置投融资知识单元数据权限实体。"""
    entities = [e.model_dump() for e in payload.entities]
    permission_service.configure_unit_permissions(db, unit_id, entities)
    return {"unit_id": unit_id, "configured": len(entities)}


@router.post("/check-permissions", response_model=CheckPermissionsResponse)
def check_permissions(payload: CheckPermissionsRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """批量校验数据权限：请求 user_id、unit_ids，响应 authorized/unauthorized。"""
    return permission_service.check_permissions(db, payload.user_id, payload.unit_ids)


@router.post("/reindex")
def reindex(
    user: dict = Depends(get_current_user),
    status: str = "active",
    batch_size: int = 32,
    index_status: str | None = None,
):
    """重建向量索引（Milvus 向量 + ES 关键字 BM25；Milvus 故障恢复 / 索引迁移）。

    后台异步执行，返回 task_id 供轮询。status=all 表示不过滤实体状态；
    index_status 可按索引状态（pending/indexed/failed）重建缺失/失败的索引。
    """
    status_filter = None if status == "all" else status
    task_id = knowledge_service.trigger_reindex(
        status_filter, batch_size, index_status_filter=index_status
    )
    return {"task_id": task_id}


@router.get("/reindex/{task_id}")
def reindex_status(task_id: str, user: dict = Depends(get_current_user)):
    """轮询向量索引重建任务进度。"""
    return knowledge_service.get_reindex_status(task_id)