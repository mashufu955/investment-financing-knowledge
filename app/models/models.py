"""SQLAlchemy ORM 模型：对应 database/init.sql 中的全部数据表。

骨架阶段仅声明表结构与字段，未实现关联/校验逻辑。
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import (
    DECIMAL,
    MEDIUMTEXT,
    TINYINT,
)

from app.core.database import Base


class User(Base):
    """内部员工（对应 02 技能：users 表）。"""

    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    display_name = Column(String(64), nullable=False)
    department_id = Column(BigInteger, nullable=True)
    status = Column(Integer, nullable=False, default=1)  # 1 启用 0 停用
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Department(Base):
    """团队/基金/项目范围（树形）。"""

    __tablename__ = "departments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    parent_id = Column(BigInteger, nullable=True)
    name = Column(String(128), nullable=False)
    dept_type = Column(String(32), nullable=True, comment='分类: team/fund/project/sub')
    leader_id = Column(BigInteger, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Role(Base):
    """角色。"""

    __tablename__ = "roles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    role_name = Column(String(64), nullable=False)
    role_code = Column(String(64), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class UserRole(Base):
    """用户-角色关联。"""

    __tablename__ = "user_roles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    role_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class RolePermission(Base):
    """角色-操作权限。"""

    __tablename__ = "role_permissions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    role_id = Column(BigInteger, nullable=False)
    permission_code = Column(String(128), nullable=False)
    permission_type = Column(String(32), nullable=False)  # menu / button
    created_at = Column(DateTime, default=datetime.now)


class KnowledgeUnit(Base):
    """投融资知识单元（对应 01 技能：knowledge_units 表）。"""

    __tablename__ = "knowledge_units"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    unit_code = Column(String(64), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(MEDIUMTEXT, nullable=True)
    summary = Column(String(1000), nullable=True)
    category = Column(String(64), nullable=True)
    source_file_name = Column(String(255), nullable=True)
    file_type = Column(String(16), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    # 投融资扩展字段
    industry = Column(String(64), nullable=True)
    financing_round = Column(String(32), nullable=True)
    amount = Column(DECIMAL(18, 2), nullable=True)
    currency = Column(String(8), nullable=True)
    valuation = Column(DECIMAL(18, 2), nullable=True)
    region = Column(String(64), nullable=True)
    deal_stage = Column(String(32), nullable=True)
    confidential_level = Column(TINYINT, nullable=False, default=1)
    # 通用字段
    status = Column(String(32), nullable=False, default="active")
    version = Column(Integer, nullable=False, default=1)
    # 向量索引同步状态（MySQL 主数据、Milvus/ES 从索引；pending/indexed/failed）
    index_status = Column(String(16), nullable=False, default="pending")
    vector_synced_at = Column(DateTime, nullable=True)
    creator_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class UnitPermission(Base):
    """知识单元数据权限（四维：global / department / role / user）。"""

    __tablename__ = "unit_permissions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    unit_id = Column(BigInteger, nullable=False)
    target_type = Column(String(16), nullable=False)
    target_id = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now)


class QaSession(Base):
    """问答会话。"""

    __tablename__ = "qa_sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(36), unique=True, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class QaMessage(Base):
    """问答消息。"""

    __tablename__ = "qa_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False)
    role = Column(String(16), nullable=False)  # user / assistant
    content = Column(MEDIUMTEXT, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class QaAccessLog(Base):
    """问答访问日志（对应 04 技能：qa_access_logs 表）。"""

    __tablename__ = "qa_access_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=True)
    user_id = Column(BigInteger, nullable=False)
    question = Column(Text, nullable=True)
    answer = Column(MEDIUMTEXT, nullable=True)
    recalled_unit_ids_json = Column(JSON, nullable=True)
    authorized_unit_ids_json = Column(JSON, nullable=True)
    unauthorized_unit_ids_json = Column(JSON, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class Faq(Base):
    """FAQ（对应 05 技能：faqs 表）。"""

    __tablename__ = "faqs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    question = Column(String(500), nullable=False)
    answer = Column(MEDIUMTEXT, nullable=True)
    category = Column(String(64), nullable=True)
    related_unit_id = Column(BigInteger, nullable=True)
    source_type = Column(String(32), nullable=False, default="manual")
    status = Column(String(32), nullable=False, default="pending_review")
    hit_count = Column(Integer, nullable=False, default=0)
    reviewer_id = Column(BigInteger, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class KnowledgeGap(Base):
    """知识缺口（对应 05 技能：knowledge_gaps 表）。"""

    __tablename__ = "knowledge_gaps"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    question_pattern = Column(String(500), nullable=False)
    sample_questions_json = Column(JSON, nullable=True)
    ask_count = Column(Integer, nullable=False, default=1)
    last_asked_at = Column(DateTime, default=datetime.now)
    status = Column(String(32), nullable=False, default="unresolved")
    resolved_unit_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
