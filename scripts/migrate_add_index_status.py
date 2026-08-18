"""运维脚本：为 knowledge_units 表新增 index_status / vector_synced_at 列（幂等）。

背景：knowledge_units 表此前无向量索引同步状态字段；新增 index_status
（pending/indexed/failed）与 vector_synced_at 用于追踪 MySQL 主数据与 Milvus/ES
从索引的同步状态，支持 failed 兜底重建。

幂等：先查 information_schema，列不存在才 ALTER；可重复执行。

用法（在 backend 容器内执行，镜像已自带本脚本于 /app/scripts）：
    python scripts/migrate_add_index_status.py
"""
import os
import sys

# 确保能从脚本所在目录（/app/scripts）找到 app 包（/app）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import text

from app.core.database import SessionLocal


def main() -> int:
    db = SessionLocal()
    try:
        cols = [
            r[0]
            for r in db.execute(
                text(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'knowledge_units'"
                )
            ).all()
        ]
        added: list[str] = []
        if "index_status" not in cols:
            db.execute(
                text(
                    "ALTER TABLE knowledge_units "
                    "ADD COLUMN index_status VARCHAR(16) NOT NULL DEFAULT 'pending' "
                    "COMMENT '向量索引状态 pending/indexed/failed'"
                )
            )
            added.append("index_status")
        if "vector_synced_at" not in cols:
            db.execute(
                text(
                    "ALTER TABLE knowledge_units "
                    "ADD COLUMN vector_synced_at DATETIME NULL COMMENT '向量同步时间'"
                )
            )
            added.append("vector_synced_at")
        # 确保存在索引（MySQL 不支持 ADD INDEX IF NOT EXISTS，忽略已存在报错）
        if "index_status" in added:
            try:
                db.execute(
                    text(
                        "ALTER TABLE knowledge_units ADD INDEX idx_index_status (index_status)"
                    )
                )
            except Exception:  # noqa: BLE001
                pass
        db.commit()
        if added:
            print(f"已新增列: {added}")
        else:
            print("列已存在，无需变更。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
