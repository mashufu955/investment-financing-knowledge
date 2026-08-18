"""补救脚本：为已存在但缺少数据权限记录的公开级知识单元补写默认权限。

背景：
    旧导入流程（import_documents / create_unit）从未写入 unit_permissions，
    导致 AI 问答按 deny-by-default 拦截，出现"以下内容因缺少项目数据权限未纳入回答"。
    本脚本为 confidential_level<=1（含 NULL 视为公开）且无权限记录的单元补写：
      - target_type="global"  全局可读
      - target_type="user"    创建者本人可读（creator_id 存在时）

运行（务必在 backend 容器内执行，复用容器内网络与凭证）：
    cd docker-investment-financing
    docker compose --env-file ../.env exec backend python scripts/backfill_unit_permissions.py --dry-run
    docker compose --env-file ../.env exec backend python scripts/backfill_unit_permissions.py
"""
import argparse
import logging

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.models import KnowledgeUnit, UnitPermission

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def backfill(dry_run: bool = False) -> int:
    """返回需要/已补写权限的单元数量。"""
    db = SessionLocal()
    try:
        # confidential_level 为 NULL 或 <=1 视为公开级，需要兜底可读
        units = db.execute(
            select(KnowledgeUnit).where(
                (KnowledgeUnit.confidential_level.is_(None))
                | (KnowledgeUnit.confidential_level <= 1)
            )
        ).scalars().all()

        fixed = 0
        for unit in units:
            existing = db.execute(
                select(UnitPermission).where(UnitPermission.unit_id == unit.id)
            ).scalars().all()
            if existing:
                continue
            creator_id = unit.creator_id or 0
            logger.info("补写权限 unit_code=%s id=%s creator_id=%s", unit.unit_code, unit.id, creator_id)
            if not dry_run:
                db.add(UnitPermission(unit_id=unit.id, target_type="global", target_id=0))
                if creator_id:
                    db.add(UnitPermission(unit_id=unit.id, target_type="user", target_id=creator_id))
            fixed += 1

        if not dry_run and fixed:
            db.commit()
        logger.info("完成：%s 个单元%s权限（dry_run=%s）", fixed, "已补写" if not dry_run else "待补写", dry_run)
        return fixed
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="为缺权限的公开级知识单元补写默认权限")
    parser.add_argument("--dry-run", action="store_true", help="只统计需要补写的单元，不写入数据库")
    args = parser.parse_args()
    backfill(dry_run=args.dry_run)
