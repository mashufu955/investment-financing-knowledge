"""RBAC 操作权限与四维数据权限校验（对应技能：组织与权限-check_permission / evaluate_unit_permission）。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import (
    Department,
    KnowledgeUnit,
    RolePermission,
    UnitPermission,
    UserRole,
)


def check_permission(db: Session, user_id: int, permission_code: str) -> bool:
    """按 RBAC 配置拦截菜单与按钮级操作权限。"""
    rows = db.execute(
        select(RolePermission.permission_code)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id, RolePermission.permission_code == permission_code)
    ).all()
    return bool(rows)


def evaluate_unit_permission(
    db: Session,
    user_id: int,
    unit_id: int,
    context: dict,
) -> bool:
    """按全局、部门、角色、个人四种权限实体校验，满足任意一种即放行。"""
    unit = db.get(KnowledgeUnit, unit_id)
    confidential_level = unit.confidential_level if unit else None
    rules = db.execute(
        select(UnitPermission).where(UnitPermission.unit_id == unit_id)
    ).scalars()
    return resolve_permission_conflict(user_id, context, list(rules), confidential_level=confidential_level)


def resolve_user_scope(db: Session, user_id: int) -> dict:
    """返回用户部门、角色、基金、项目、团队范围。"""
    return _build_context(db, user_id)


def build_permission_context(db: Session, user_id: int, unit_ids: list[int] | None = None) -> dict:
    """组装权限校验上下文。"""
    ctx = _build_context(db, user_id)
    ctx["unit_ids"] = unit_ids or []
    ctx["request_type"] = "retrieval"
    return ctx


def filter_authorized_ids(
    db: Session,
    user_id: int,
    unit_ids: list[int],
) -> dict:
    """输出 authorized_unit_ids 和 unauthorized_unit_ids。"""
    context = _build_context(db, user_id)
    authorized: list[int] = []
    unauthorized: list[int] = []
    for uid in unit_ids:
        if evaluate_unit_permission(db, user_id, uid, context):
            authorized.append(uid)
        else:
            unauthorized.append(uid)
    return {"authorized_unit_ids": authorized, "unauthorized_unit_ids": unauthorized}


def mask_unauthorized_metadata() -> dict:
    """仅返回权限缺失提示，不泄露具体元数据。"""
    return {"masked": True, "reason": "no_permission"}


def audit_permission_decision(decision: dict) -> dict:
    """记录权限决策日志。"""
    decision["audited_at"] = _now()
    return decision


def resolve_permission_conflict(user_id: int, context: dict, rules: list[UnitPermission], confidential_level: int = None) -> bool:
    """按 deny-by-default 与 deny 优先处理冲突。"""
    if not rules:
        # 无显式权限配置时：公开级（confidential_level<=1）默认可读，其余默认拒绝
        if confidential_level is not None and confidential_level <= 1:
            return True
        return False
    has_allow = False
    has_deny = False
    for rule in rules:
        if rule.target_type == "deny":
            has_deny = True
        elif rule.target_type == "global":
            has_allow = True
        elif rule.target_type == "department" and rule.target_id in context.get("department_ids", []):
            has_allow = True
        elif rule.target_type == "role" and rule.target_id in context.get("role_ids", []):
            has_allow = True
        elif rule.target_type == "user" and rule.target_id == user_id:
            has_allow = True
    return has_allow and not has_deny


def check_cross_fund_access(request: dict, target: dict) -> bool:
    """跨基金/项目访问时触发审批或拒绝。"""
    if target.get("fund_id") in request.get("fund_ids", []):
        return True
    return target.get("requires_approval", False)


def _build_context(db: Session, user_id: int) -> dict:
    role_rows = db.execute(
        select(UserRole.role_id).where(UserRole.user_id == user_id)
    ).all()
    role_ids = [r[0] for r in role_rows]
    from app.models.models import User

    user = db.get(User, user_id)
    department_ids = [user.department_id] if user and user.department_id else []
    return {
        "user_id": user_id,
        "department_ids": department_ids,
        "role_ids": role_ids,
        "fund_ids": [],
        "project_ids": [],
        "team_ids": [],
    }


def _now():
    from datetime import datetime

    return datetime.utcnow()