"""数据看板接口：/api/dashboard/*。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.services.dashboard_service import dashboard_service

router = APIRouter()


@router.get("/metrics")
def get_metrics(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询访问总次数、独立用户数、知识单元数、Token 总量与平均耗时。"""
    return dashboard_service.get_metrics(db)


@router.get("/project-pipeline")
def get_project_pipeline_metrics(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询项目数量、阶段分布、融资金额与行业分布。"""
    return dashboard_service.get_project_pipeline_metrics(db)


@router.get("/rankings/questions")
def get_question_rankings(top_n: int = 10, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询投融资常见问题 TOP 榜。"""
    return dashboard_service.get_question_rankings(db, top_n)


@router.get("/rankings/units")
def get_unit_rankings(top_n: int = 10, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询最常访问项目知识单元 TOP 榜。"""
    return dashboard_service.get_unit_rankings(db, top_n)


@router.get("/stats/tokens")
def get_token_stats(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询 Token 消耗与响应时间趋势。"""
    return dashboard_service.get_token_stats(db)