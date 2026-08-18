"""认证接口：POST /api/auth/login。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.schemas import LoginRequest, LoginResponse, UserInfo
from app.services.auth_service import auth_service

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """内部员工登录。"""
    return auth_service.login(db, payload.username, payload.password)


@router.get("/me", response_model=UserInfo)
def me(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前登录用户信息。"""
    user_id = int(user["user_id"])
    return auth_service.get_current_user(db, user_id)