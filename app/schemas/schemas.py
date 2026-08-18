"""Pydantic 请求/响应模型（骨架阶段声明主要字段，校验规则待补充）。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==================== 认证 ====================
class LoginRequest(BaseModel):
    username: str = Field(..., description="登录名")
    password: str = Field(..., description="密码")


class UserInfo(BaseModel):
    id: int
    username: str
    display_name: str
    department_id: Optional[int] = None
    roles: list[str] = []
    permissions: list[str] = []


class LoginResponse(BaseModel):
    access_token: str
    user_info: UserInfo
    permissions: list[str] = []


# ==================== 组织与权限 ====================
class DepartmentNode(BaseModel):
    id: int
    parent_id: Optional[int] = None
    name: str
    dept_type: Optional[str] = None
    leader_id: Optional[int] = None
    leader_name: Optional[str] = None
    member_count: int = 0
    sort_order: int = 0
    children: list["DepartmentNode"] = []


class UserCreateRequest(BaseModel):
    username: str
    password: str
    display_name: str
    department_id: Optional[int] = None
    role_ids: list[int] = []


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    department_id: Optional[int] = None
    status: Optional[int] = None
    role_ids: list[int] = []


class RoleCreateRequest(BaseModel):
    role_name: str
    role_code: str
    description: Optional[str] = None


class RolePermissionRequest(BaseModel):
    permissions: list[str] = Field(..., description="权限编码列表")


# ==================== 投融资知识维护 ====================
class UnitCreateRequest(BaseModel):
    title: str
    content: str = ""
    summary: Optional[str] = None
    category: Optional[str] = None
    industry: Optional[str] = None
    financing_round: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    valuation: Optional[float] = None
    region: Optional[str] = None
    deal_stage: Optional[str] = None
    confidential_level: int = 1
    status: str = "active"
    gap_id: Optional[int] = None


class UnitUpdateRequest(UnitCreateRequest):
    pass


class UnitQueryParams(BaseModel):
    industry: Optional[str] = None
    financing_round: Optional[str] = None
    deal_stage: Optional[str] = None
    confidential_level: Optional[int] = None
    status: Optional[str] = None
    page: int = 1
    page_size: int = 20


class UnitListItem(BaseModel):
    id: int
    unit_code: str
    title: str
    industry: Optional[str] = None
    financing_round: Optional[str] = None
    deal_stage: Optional[str] = None
    confidential_level: int
    creator_id: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: datetime


class UnitDetail(UnitListItem):
    content: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    permission_summary: list[dict] = []


class ImportResponse(BaseModel):
    task_id: str
    total_files: int


# ==================== 数据权限 ====================
class PermissionEntity(BaseModel):
    target_type: str = Field(..., description="global / department / role / user")
    target_id: int = 0


class ConfigureUnitPermissionsRequest(BaseModel):
    entities: list[PermissionEntity]


class CheckPermissionsRequest(BaseModel):
    user_id: int
    unit_ids: list[int]


class CheckPermissionsResponse(BaseModel):
    authorized_unit_ids: list[int]
    unauthorized_unit_ids: list[int]


# ==================== AI 问答 ====================
class ChatStreamRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


# ==================== 知识沉淀与 FAQ ====================
class FaqReviewRequest(BaseModel):
    action: str = Field(..., description="approve / reject")
    edited_answer: Optional[str] = None


class GapResolveRequest(BaseModel):
    action: str = Field(..., description="resolve / reject")
    resolved_unit_id: Optional[int] = None
