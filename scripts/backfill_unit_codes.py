"""运维脚本：存量知识单元重编号 + 行业中文化（幂等）。

背景：知识单元编号规则统一为「年月日(YYYYMMDD) + 4 位当日序号」，如 202608180001；
行业统一以中文命名。本脚本对已有 knowledge_units 做一次补齐：
  1. 按各单元 created_at 的日期 + 当日序号重算 unit_code（保证日期内唯一、跨日期前缀不同）；
  2. 用 normalize_industry 将行业字段由英文 code / 中文别名归一成中文规范名。
编号/行业均为幂等：重跑不会改变已正确的值（除非日期序号规则变化）。

用法（在 backend 容器内执行，镜像已自带本脚本于 /app/scripts）：
    python scripts/backfill_unit_codes.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from datetime import datetime

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.models import KnowledgeUnit
from app.services.knowledge_service import knowledge_service


def main() -> int:
    db = SessionLocal()
    try:
        units = db.execute(
            select(KnowledgeUnit)
            .order_by(KnowledgeUnit.created_at, KnowledgeUnit.id)
        ).scalars().all()

        day_seq: dict[str, int] = {}
        reassigned = 0
        industry_fixed = 0
        for u in units:
            # 1) 重编号：以 created_at 日期为前缀 + 当日自增序号
            base_dt = u.created_at or datetime.now()
            prefix = base_dt.strftime("%Y%m%d")
            day_seq[prefix] = day_seq.get(prefix, 0) + 1
            new_code = f"{prefix}{day_seq[prefix]:04d}"
            if u.unit_code != new_code:
                u.unit_code = new_code
                reassigned += 1

            # 2) 行业中文化：英文 code / 中文别名 → 中文规范名
            if u.industry:
                new_industry = knowledge_service.normalize_industry(u.industry)
                if new_industry != u.industry:
                    u.industry = new_industry
                    industry_fixed += 1

        db.commit()
        print(f"存量单元总数: {len(units)}")
        print(f"重编号单元数: {reassigned}")
        print(f"行业中文化单元数: {industry_fixed}")
        print("done.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
