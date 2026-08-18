"""组织与权限接口：/api/org/*。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.core.database import get_db
from app.schemas.schemas import (
    DepartmentNode,
    RoleCreateRequest,
    RolePermissionRequest,
    UserCreateRequest,
    UserUpdateRequest,
)
from app.services.org_service import org_service

router = APIRouter()


@router.get("/departments", response_model=list[DepartmentNode])
def list_departments(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取团队/基金/项目范围树形列表。"""
    return org_service.list_departments(db)


@router.post("/departments")
def create_department(payload: dict, user: dict = Depends(require_permission("org:dept:manage")), db: Session = Depends(get_db)):
    """新增投资团队、基金或项目组节点。"""
    return org_service.create_department(db, payload)


@router.put("/departments/{dept_id}")
def update_department(dept_id: int, payload: dict, user: dict = Depends(require_permission("org:dept:manage")), db: Session = Depends(get_db)):
    """编辑团队/基金/项目组。"""
    return org_service.update_department(db, dept_id, payload)


@router.delete("/departments/{dept_id}")
def delete_department(dept_id: int, user: dict = Depends(require_permission("org:dept:manage")), db: Session = Depends(get_db)):
    """删除团队/基金/项目组节点。"""
    org_service.delete_department(db, dept_id)
    return {"id": dept_id}


@router.post("/departments/{dept_id}/members")
def assign_department_members(dept_id: int, user_ids: list[int], user: dict = Depends(require_permission("org:dept:manage")), db: Session = Depends(get_db)):
    """维护团队成员关联。"""
    org_service.assign_department_members(db, dept_id, user_ids)
    return {"dept_id": dept_id, "user_ids": user_ids}


@router.post("/users")
def create_user(payload: UserCreateRequest, user: dict = Depends(require_permission("org:user:manage")), db: Session = Depends(get_db)):
    """新增内部员工。"""
    return org_service.create_user(db, payload.model_dump())


@router.get("/users")
def list_users(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取内部员工列表（含团队归属、角色关联）。"""
    return org_service.list_users(db)


@router.put("/users/{user_id}")
def update_user(user_id: int, payload: UserUpdateRequest, user: dict = Depends(require_permission("org:user:manage")), db: Session = Depends(get_db)):
    """编辑内部员工。"""
    return org_service.update_user(db, user_id, payload.model_dump())


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, payload: dict, user: dict = Depends(require_permission("org:user:manage")), db: Session = Depends(get_db)):
    """重置员工密码。"""
    org_service.reset_password(db, user_id, payload["new_password"])
    return {"user_id": user_id}


@router.post("/users/{user_id}/status")
def enable_disable_user(user_id: int, payload: dict, user: dict = Depends(require_permission("org:user:manage")), db: Session = Depends(get_db)):
    """启停用员工账号。"""
    org_service.enable_disable_user(db, user_id, bool(payload.get("enable", True)))
    return {"user_id": user_id}


@router.get("/roles")
def list_roles(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取角色列表。"""
    return org_service.list_roles(db)


@router.post("/roles")
def create_role(payload: RoleCreateRequest, user: dict = Depends(require_permission("org:role:manage")), db: Session = Depends(get_db)):
    """新增角色。"""
    return org_service.create_role(db, payload.model_dump())


@router.put("/roles/{role_id}")
def update_role(role_id: int, payload: RoleCreateRequest, user: dict = Depends(require_permission("org:role:manage")), db: Session = Depends(get_db)):
    """更新角色。"""
    return org_service.update_role(db, role_id, payload.model_dump())


@router.delete("/roles/{role_id}")
def delete_role(role_id: int, user: dict = Depends(require_permission("org:role:manage")), db: Session = Depends(get_db)):
    """删除角色。"""
    org_service.delete_role(db, role_id)
    return {"role_id": role_id}


@router.post("/roles/{role_id}/permissions")
def assign_role_permissions(role_id: int, payload: RolePermissionRequest, user: dict = Depends(require_permission("org:role:manage")), db: Session = Depends(get_db)):
    """分配角色操作权限树。"""
    org_service.assign_role_permissions(db, role_id, payload.permissions)
    return {"role_id": role_id, "assigned": len(payload.permissions)}