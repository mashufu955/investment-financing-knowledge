"""02-组织与权限：团队/基金/项目范围、员工与角色管理（技能文档 02）。"""
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.models import (
    Department,
    Role,
    RolePermission,
    User,
    UserRole,
)


class OrgService:
    """组织与角色管理服务。"""

    # ============ 团队/基金/项目范围 ============
    def list_departments(self, db: Session) -> list:
        """GET /api/org/departments：获取团队/基金/项目范围树形列表（含负责人姓名与成员数）。"""
        rows = list(db.execute(select(Department).order_by(Department.sort_order)).scalars())
        dept_ids = [d.id for d in rows]
        leader_ids = [d.leader_id for d in rows if d.leader_id]
        # 负责人姓名
        leader_map: dict[int, str] = {}
        if leader_ids:
            for lid, name in db.execute(
                select(User.id, User.display_name).where(User.id.in_(leader_ids))
            ).all():
                leader_map[lid] = name
        # 各节点成员数（按 department_id 统计启用用户）
        count_map: dict[int, int] = {}
        if dept_ids:
            for did, cnt in db.execute(
                select(User.department_id, func.count(User.id))
                .where(User.department_id.in_(dept_ids), User.status == 1)
                .group_by(User.department_id)
            ).all():
                count_map[did] = cnt
        items = [
            {
                "id": d.id,
                "parent_id": d.parent_id,
                "name": d.name,
                "dept_type": d.dept_type,
                "leader_id": d.leader_id,
                "leader_name": leader_map.get(d.leader_id) if d.leader_id else None,
                "member_count": count_map.get(d.id, 0),
                "sort_order": d.sort_order,
            }
            for d in rows
        ]
        return _build_dept_tree(items)

    def create_department(self, db: Session, data: dict) -> dict:
        """新增投资团队、基金或项目组节点。"""
        dept = Department(
            parent_id=data.get("parent_id"),
            name=data["name"],
            dept_type=data.get("dept_type"),
            leader_id=data.get("leader_id"),
            sort_order=data.get("sort_order", 0),
        )
        db.add(dept)
        db.commit()
        db.refresh(dept)
        return {"id": dept.id, "name": dept.name}

    def update_department(self, db: Session, dept_id: int, data: dict) -> dict:
        """编辑团队/基金/项目组名称、负责人与排序。"""
        dept = db.get(Department, dept_id)
        for k in ("name", "dept_type", "leader_id", "sort_order", "parent_id"):
            if k in data:
                setattr(dept, k, data[k])
        db.commit()
        return {"id": dept.id, "name": dept.name}

    def delete_department(self, db: Session, dept_id: int) -> None:
        """删除团队/基金/项目组节点（校验是否存在下级与成员）。"""
        has_child = db.execute(
            select(Department.id).where(Department.parent_id == dept_id).limit(1)
        ).scalar()
        if has_child:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "存在子节点，无法删除")
        has_member = db.execute(
            select(User.id).where(User.department_id == dept_id).limit(1)
        ).scalar()
        if has_member:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "存在员工，无法删除")
        dept = db.get(Department, dept_id)
        db.delete(dept)
        db.commit()

    def assign_department_members(self, db: Session, dept_id: int, user_ids: list[int]) -> None:
        """维护团队成员关联。"""
        for uid in user_ids:
            user = db.get(User, uid)
            if user:
                user.department_id = dept_id
        db.commit()

    # ============ 内部员工 ============
    def list_users(self, db: Session) -> list:
        """获取内部员工列表（含团队归属、角色关联）。"""
        rows = db.execute(select(User)).scalars()
        items = []
        for u in rows:
            role_codes = db.execute(
                select(Role.role_code)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == u.id)
            ).all()
            items.append(
                {
                    "id": u.id,
                    "username": u.username,
                    "display_name": u.display_name,
                    "department_id": u.department_id,
                    "status": u.status,
                    "roles": [r[0] for r in role_codes],
                }
            )
        return items

    def create_user(self, db: Session, data: dict) -> dict:
        """POST /api/org/users：新增内部员工。"""
        if db.execute(select(User).where(User.username == data["username"])).scalar():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "登录名已存在")
        user = User(
            username=data["username"],
            password_hash=hash_password(data["password"]),
            display_name=data["display_name"],
            department_id=data.get("department_id"),
            status=1,
        )
        db.add(user)
        db.flush()
        for rid in data.get("role_ids", []):
            db.add(UserRole(user_id=user.id, role_id=rid))
        db.commit()
        db.refresh(user)
        return {"id": user.id, "username": user.username}

    def update_user(self, db: Session, user_id: int, data: dict) -> dict:
        """PUT /api/org/users/{id}：编辑内部员工信息与角色关联。"""
        user = db.get(User, user_id)
        for k in ("display_name", "department_id", "status"):
            if k in data:
                setattr(user, k, data[k])
        if "role_ids" in data:
            db.execute(delete(UserRole).where(UserRole.user_id == user_id))
            for rid in data["role_ids"]:
                db.add(UserRole(user_id=user_id, role_id=rid))
        db.commit()
        return {"id": user.id}

    def reset_password(self, db: Session, user_id: int, new_password: str) -> None:
        """重置员工密码。"""
        user = db.get(User, user_id)
        user.password_hash = hash_password(new_password)
        db.commit()

    def enable_disable_user(self, db: Session, user_id: int, enable: bool) -> None:
        """启停用员工账号。"""
        user = db.get(User, user_id)
        user.status = 1 if enable else 0
        db.commit()

    # ============ 角色 ============
    def list_roles(self, db: Session) -> list:
        """GET /api/org/roles：获取角色列表（含各角色当前权限编码）。"""
        rows = list(db.execute(select(Role).order_by(Role.id)).scalars())
        role_ids = [r.id for r in rows]
        perm_rows = (
            db.execute(
                select(RolePermission.role_id, RolePermission.permission_code).where(
                    RolePermission.role_id.in_(role_ids)
                )
            ).all()
            if role_ids
            else []
        )
        perm_map: dict[int, list[str]] = {}
        for role_id, code in perm_rows:
            perm_map.setdefault(role_id, []).append(code)
        return [
            {
                "id": r.id,
                "role_name": r.role_name,
                "role_code": r.role_code,
                "description": r.description,
                "permissions": perm_map.get(r.id, []),
            }
            for r in rows
        ]

    def create_role(self, db: Session, data: dict) -> dict:
        """维护角色名称、角色编码，例如投资经理、投委会、风控、法务、财务、运营。"""
        if db.execute(select(Role).where(Role.role_code == data["role_code"])).scalar():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "角色编码已存在")
        role = Role(
            role_name=data["role_name"],
            role_code=data["role_code"],
            description=data.get("description"),
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        return {"id": role.id, "role_code": role.role_code}

    def update_role(self, db: Session, role_id: int, data: dict) -> dict:
        """更新角色名称、角色编码。"""
        role = db.get(Role, role_id)
        for k in ("role_name", "role_code", "description"):
            if k in data:
                setattr(role, k, data[k])
        db.commit()
        return {"id": role.id}

    def delete_role(self, db: Session, role_id: int) -> None:
        """删除角色（校验关联用户与权限）。"""
        if db.execute(select(UserRole.id).where(UserRole.role_id == role_id).limit(1)).scalar():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "角色存在关联用户")
        db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        db.delete(db.get(Role, role_id))
        db.commit()

    def assign_role_permissions(self, db: Session, role_id: int, permissions: list[str]) -> None:
        """POST /api/org/roles/{id}/permissions：分配角色操作权限树。"""
        db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        for code in permissions:
            db.add(RolePermission(role_id=role_id, permission_code=code, permission_type="button"))
        db.commit()

    # ============ 上下文 ============
    def resolve_user_context(self, db: Session, user_id: int) -> dict:
        """获取用户所属团队、基金/项目范围与角色列表，供数据权限校验使用。"""
        user = db.get(User, user_id)
        rows = db.execute(select(UserRole.role_id).where(UserRole.user_id == user_id)).all()
        return {
            "user_id": user_id,
            "department_ids": [user.department_id] if user.department_id else [],
            "role_ids": [r[0] for r in rows],
            "is_admin": False,
        }


def _build_dept_tree(items: list[dict]) -> list[dict]:
    lookup = {it["id"]: {**it, "children": []} for it in items}
    roots: list[dict] = []
    for it in lookup.values():
        if it["parent_id"] and it["parent_id"] in lookup:
            lookup[it["parent_id"]]["children"].append(it)
        else:
            roots.append(it)
    return roots


org_service = OrgService()