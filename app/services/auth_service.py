"""02-组织与权限：登录认证（技能文档 02：登录 / 签发 / 校验）。"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import check_permission, resolve_user_scope
from app.core.security import issue_token as issue_jwt
from app.core.security import verify_password, verify_token as verify_jwt
from app.models.models import RolePermission, User, UserRole


class AuthService:
    """认证服务：登录、签发令牌、校验登录态。"""

    def login(self, db: Session, username: str, password: str) -> dict:
        """POST /api/auth/login：内部员工登录。"""
        user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
        if user.status != 1:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
        permissions = self._load_permissions(db, user.id)
        token = self.issue_token(user.id, user.username)
        return {
            "access_token": token,
            "user_info": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "department_id": user.department_id,
                "roles": self._load_role_codes(db, user.id),
                "permissions": permissions,
            },
            "permissions": permissions,
        }

    def issue_token(self, user_id: int, username: str) -> str:
        """签发 JWT 令牌。"""
        return issue_jwt(user_id, username)

    def verify_token(self, token: str) -> dict:
        """校验 JWT 令牌与用户登录态。"""
        return verify_jwt(token)

    def get_current_user(self, db: Session, user_id: int) -> dict:
        """查询当前用户身份、所属团队、基金/项目范围与拥有角色。"""
        user = db.get(User, user_id)
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "department_id": user.department_id,
            "roles": self._load_role_codes(db, user.id),
            "permissions": self._load_permissions(db, user.id),
        }

    def resolve_user_context(self, db: Session, user_id: int) -> dict:
        """获取用户所属团队、基金/项目范围与角色列表。"""
        return resolve_user_scope(db, user_id)

    def _load_permissions(self, db: Session, user_id: int) -> list[str]:
        rows = db.execute(
            select(RolePermission.permission_code)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id)
        ).all()
        return sorted({r[0] for r in rows})

    def _load_role_codes(self, db: Session, user_id: int) -> list[str]:
        from app.models.models import Role

        rows = db.execute(
            select(Role.role_code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        ).all()
        return [r[0] for r in rows]


auth_service = AuthService()