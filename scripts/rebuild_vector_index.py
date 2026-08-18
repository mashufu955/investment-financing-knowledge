"""运维脚本：重建知识单元向量索引（Milvus 向量 + ES 关键字 BM25）。

适用场景：
- Milvus 故障恢复：此前导入因 Milvus 不可用导致「数据已入库但向量索引缺失」，
  恢复 Milvus 后运行本脚本补齐向量索引。
- 索引迁移 / 集合 schema 变更后全量重建。

用法（在 backend 容器内执行，镜像已自带本脚本于 /app/scripts）：
    python scripts/rebuild_vector_index.py               # 重建 status=active 的单元
    python scripts/rebuild_vector_index.py --status all  # 重建全部（不过滤状态）
    python scripts/rebuild_vector_index.py --status draft  # 仅重建 draft
    python scripts/rebuild_vector_index.py --batch-size 16  # 自定义批次大小
    python scripts/rebuild_vector_index.py --dry-run     # 仅统计数量，不写索引
    python scripts/rebuild_vector_index.py --index-status failed  # 仅重建索引状态为 failed 的单元
"""
import argparse
import os
import sys

# 确保能从脚本所在目录（/app/scripts）找到 app 包（/app）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.models import KnowledgeUnit
from app.services.knowledge_service import knowledge_service


def main() -> int:
    parser = argparse.ArgumentParser(description="重建知识单元向量索引（Milvus + ES 关键字）")
    parser.add_argument(
        "--status",
        default="active",
        help="按状态过滤：active / draft / all；all 表示不过滤（默认 active）",
    )
    parser.add_argument("--batch-size", type=int, default=32, help="向量化批次大小（默认 32）")
    parser.add_argument(
        "--index-status",
        default=None,
        help="按索引状态过滤重建：pending / indexed / failed；优先于 --status（默认 None 不按索引状态过滤）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅统计匹配的知识单元数量，不写入索引",
    )
    args = parser.parse_args()

    status_filter = None if args.status == "all" else args.status
    index_status_filter = args.index_status
    db = SessionLocal()
    try:
        if args.dry_run:
            stmt = select(KnowledgeUnit)
            if index_status_filter:
                stmt = stmt.where(KnowledgeUnit.index_status == index_status_filter)
            elif status_filter:
                stmt = stmt.where(KnowledgeUnit.status == status_filter)
            total = len(db.execute(stmt).scalars().all())
            print(
                f"[dry-run] 匹配知识单元数: {total}（index_status={index_status_filter or 'all'}, status={status_filter or 'all'}）"
            )
            return 0

        def on_progress(done: int, total: int) -> None:
            print(f"  进度: {done}/{total}", flush=True)

        print(
            f"开始重建向量索引（status={status_filter or 'all'}, batch_size={args.batch_size}）…"
        )
        result = knowledge_service.rebuild_vector_index(
            db,
            status_filter=status_filter,
            batch_size=args.batch_size,
            on_progress=on_progress,
            index_status_filter=index_status_filter,
        )
        print(
            f"\n重建完成: total={result['total']}, "
            f"indexed={result['indexed']}, failed={len(result['failed'])}"
        )
        if result["failed"]:
            print(f"失败 unit ids: {result['failed']}")
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())


# cd docker-investment-financing
# 全量重建（覆盖所有状态单元，最稳妥；编辑过哪个都包含）
# docker compose --env-file ../.env exec backend python scripts/rebuild_vector_index.py --status all
# 或只重建 active（默认就是 --status active，仅覆盖 active 单元）
# docker compose --env-file ../.env exec backend python scripts/rebuild_vector_index.py