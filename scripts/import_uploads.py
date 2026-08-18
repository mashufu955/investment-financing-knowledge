"""手动导入 uploads 目录下的文档为知识单元（用于数据恢复 / 验证）。

用法（在 backend 容器内执行）：
    docker compose --env-file ../.env exec backend python scripts/import_uploads.py
    docker compose --env-file ../.env exec backend python scripts/import_uploads.py "商业航天公司A轮尽调简报"

行为：
    - 按关键词匹配 /app/uploads 下的 .md 文件，取修改时间最新的一份导入
    - 复用 KnowledgeService._process_import_background 的完整流程（解析→切片→入库→建向量/关键字索引）
    - 导入后新单元按修复后的逻辑自动写入默认权限（confidential_level<=1 全局可读 + 创建者可读）
"""
import os
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.models import User
from app.services.knowledge_service import KnowledgeService

UPLOAD_DIR = "/app/uploads"


def main() -> None:
    keyword = sys.argv[1] if len(sys.argv) > 1 else "商业航天公司A轮尽调简报"

    matched = []
    for fn in os.listdir(UPLOAD_DIR):
        if fn.lower().endswith(".md") and keyword in fn:
            matched.append((os.path.getmtime(os.path.join(UPLOAD_DIR, fn)), fn))
    if not matched:
        print(f"[import_uploads] 未找到匹配 '{keyword}' 的文件")
        return
    matched.sort()
    latest = matched[-1][1]
    path = os.path.join(UPLOAD_DIR, latest)
    size = os.path.getsize(path)
    print(f"[import_uploads] 匹配到 {len(matched)} 个文件，导入最新一份：{latest}")

    db = SessionLocal()
    try:
        user = db.execute(select(User).order_by(User.id)).scalars().first()
        creator_id = user.id if user else 1
        print(f"[import_uploads] 使用 creator_id={creator_id}")
    finally:
        db.close()

    ks = KnowledgeService()
    saved = [{"file_name": latest, "file_path": path, "file_size": size, "file_index": 0}]
    ks._process_import_background(f"manual-{os.getpid()}", saved, creator_id)
    print("[import_uploads] 导入完成（单元已入库并写入默认权限）")


if __name__ == "__main__":
    main()
