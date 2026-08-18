"""验证权限修复闭环：单元入库 + 自动授权 + 问答过滤放行。"""
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.models import KnowledgeUnit, UnitPermission
from app.services.ai_qa_service import AiQaService


def main() -> None:
    db = SessionLocal()
    try:
        units = db.execute(select(KnowledgeUnit).order_by(KnowledgeUnit.id.desc())).scalars().all()
        print(f"[verify] knowledge_units 总数: {len(units)}")
        if not units:
            print("[verify] 无单元，无法验证")
            return
        u = units[0]
        print(f"[verify] 最新单元: code={u.unit_code} title={u.title} confidential_level={u.confidential_level}")
        perms = db.execute(
            select(UnitPermission).where(UnitPermission.unit_id == u.id)
        ).scalars().all()
        print(f"[verify] 该单元权限记录: {[(p.target_type, p.target_id) for p in perms]}")

        svc = AiQaService()
        authorized, unauthorized = svc.filter_authorized_units(db, user_id=1, unit_codes=[u.unit_code])
        print(f"[verify] 问答权限过滤 -> 授权: {authorized}  拒绝: {unauthorized}")
        if authorized and not unauthorized:
            print("[verify] 结论: 修复生效，该单元在问答中可被授权召回（不再触发'缺少项目数据权限'）")
        else:
            print("[verify] 结论: 仍存在拒绝，修复未达预期")
    finally:
        db.close()


if __name__ == "__main__":
    main()
