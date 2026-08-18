"""FastAPI 依赖注入（当前用户 / RBAC 校验）。"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import get_db
from app.core.permissions import check_permission
from app.core.security import verify_token
from app.services.auth_service import auth_service
from sqlalchemy.orm import Session

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict:
    """解析请求头令牌，返回当前用户上下文。"""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    try:
        payload = verify_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc))
    return {"user_id": int(payload.get("sub")), "username": payload.get("username")}


def require_permission(permission_code: str):
    """RBAC 依赖工厂：校验用户是否具备指定操作权限。"""

    def checker(
        user: dict = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> dict:
        if not check_permission(db, int(user["user_id"]), permission_code):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
        return user

    return checker