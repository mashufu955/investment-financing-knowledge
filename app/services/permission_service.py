"""02-组织与权限：四维数据权限（技能文档 02：配置 / 校验）。"""
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.permissions import check_permission as rbac_check
from app.core.permissions import evaluate_unit_permission
from app.models.models import UnitPermission


class PermissionService:
    """数据权限服务：知识单元权限配置与批量校验。"""

    def check_permission(self, db: Session, user_id: int, permission_code: str) -> bool:
        """按 RBAC 配置拦截菜单与按钮级操作权限。"""
        return rbac_check(db, user_id, permission_code)

    def configure_unit_permissions(self, db: Session, unit_id: int, entities: list[dict]) -> None:
        """POST /api/knowledge/units/{id}/permissions：批量配置投融资知识单元数据权限实体。"""
        db.execute(delete(UnitPermission).where(UnitPermission.unit_id == unit_id))
        for ent in entities:
            db.add(
                UnitPermission(
                    unit_id=unit_id,
                    target_type=ent["target_type"],
                    target_id=ent.get("target_id", 0),
                )
            )
        db.commit()

    def check_permissions(self, db: Session, user_id: int, unit_ids: list[int]) -> dict:
        """POST /api/knowledge/check-permissions：批量校验数据权限。"""
        from app.core.permissions import build_permission_context

        context = build_permission_context(db, user_id, unit_ids)
        authorized: list[int] = []
        unauthorized: list[int] = []
        for uid in unit_ids:
            if evaluate_unit_permission(db, user_id, uid, context):
                authorized.append(uid)
            else:
                unauthorized.append(uid)
        return {"authorized_unit_ids": authorized, "unauthorized_unit_ids": unauthorized}

    def evaluate_unit_permission(self, db: Session, user_id: int, unit_id: int) -> bool:
        """按全局、部门、角色、个人四种权限实体校验，满足任意一种即放行。"""
        from app.core.permissions import build_permission_context

        context = build_permission_context(db, user_id, [unit_id])
        return evaluate_unit_permission(db, user_id, unit_id, context)


permission_service = PermissionService()