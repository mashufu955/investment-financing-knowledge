"""01-投融资知识维护：知识单元全生命周期（技能文档 01）。

覆盖单文件/批量导入、格式解析、文本切片、项目字段抽取、
知识单元 CRUD、版本与状态管理、向量化同步。
"""
import os
import re
import threading
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import SessionLocal
from app.core.es import (
    delete_unit_from_index as delete_keyword_unit,
    ensure_knowledge_index,
    index_keyword_unit,
)
from app.core.milvus import (
    delete_unit_from_index,
    ensure_knowledge_collection,
    flush_knowledge_collection,
    index_unit,
)
from app.models.models import KnowledgeUnit, UnitPermission
from app.utils.document_parser import parse_markdown, parse_pdf, parse_txt, parse_word
from app.utils.embeddings import embed_batch, embed_text
from app.utils.text_splitter import split_text

# 导入任务状态跟踪（内存级，进程重启后丢失）
_import_tasks: dict[str, dict] = {}
# 向量索引重建任务状态跟踪（内存级，进程重启后丢失）
_reindex_tasks: dict[str, dict] = {}
_task_lock = threading.Lock()


_PARSERS = {
    "pdf": parse_pdf,
    "markdown": parse_markdown,
    "md": parse_markdown,
    "word": parse_word,
    "docx": parse_word,
    "txt": parse_txt,
}

# 行业统一以中文命名：英文 code 与中文别名都映射到中文规范名；未知值原样保留（视为自定义中文）。
_INDUSTRY_CANONICAL = {
    # 英文 code → 中文
    "ai": "人工智能",
    "biotech": "生物医药",
    "semiconductor": "半导体",
    "new_energy": "新能源",
    "robotics": "机器人",
    "quantum": "量子计算",
    "low_altitude": "低空经济",
    "aerospace": "商业航天",
    "saas": "SaaS",
    "enterprise": "企业服务",
    "software": "工业软件",
    "synthetic_bio": "合成生物",
    "photoelectric": "光电芯片",
    "other": "其他",
    # 中文别名 → 中文规范名
    "人工智能": "人工智能",
    "AI": "人工智能",
    "生物医药": "生物医药",
    "创新药": "生物医药",
    "医疗": "生物医药",
    "医疗健康": "生物医药",
    "半导体": "半导体",
    "芯片": "半导体",
    "新能源": "新能源",
    "储能": "新能源",
    "机器人": "机器人",
    "量子计算": "量子计算",
    "量子": "量子计算",
    "低空经济": "低空经济",
    "eVTOL": "低空经济",
    "商业航天": "商业航天",
    "航天": "商业航天",
    "SaaS": "SaaS",
    "企业服务": "企业服务",
    "工业软件": "工业软件",
    "软件": "工业软件",
    "合成生物": "合成生物",
    "光电芯片": "光电芯片",
    "光电": "光电芯片",
}

_ROUND_SYNONYMS = {
    "种子": "seed",
    "种子轮": "seed",
    "天使": "angel",
    "天使轮": "angel",
    "pre-a": "pre_series_a",
    "pre-a轮": "pre_series_a",
    "a轮": "series_a",
    "b轮": "series_b",
    "c轮": "series_c",
    "pre-ipo": "pre_ipo",
    "战略": "strategic",
    "战略融资": "strategic",
}

_STAGE_SYNONYMS = {
    "sourcing": "sourcing",
    "线索": "sourcing",
    "尽调": "due_diligence",
    "due_diligence": "due_diligence",
    "投决": "investment_committee",
    "投委会": "investment_committee",
    "交割": "closing",
    "投后": "post_investment",
}

_ROUND_ENUM = {"seed", "angel", "series_a", "series_b", "series_c", "pre_ipo", "strategic", "other"}
_CURRENCY_ENUM = {"CNY", "USD", "HKD", "EUR", "other"}
_STAGE_ENUM = {"sourcing", "due_diligence", "investment_committee", "closing", "post_investment"}

_AMOUNT_RE = re.compile(
    r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>万|亿|百万)?\s*(?P<ccy>CNY|USD|人民币|美元|港币|港元|HKD|EUR|欧元)?",
    re.IGNORECASE,
)

_UNIT_MULT = {"万": 1e4, "亿": 1e8, "百万": 1e6}


class KnowledgeService:
    """投融资知识维护服务。"""

    def import_documents(self, db: Session, files: list, user_id: int) -> dict:
        """POST /api/knowledge/import：立即保存文件并返回 task_id，后台异步处理。

        请求线程仅做文件落盘（~毫秒级），重活（解析/切片/向量化/Milvus 写入）
        在后台线程完成，避免 HTTP 超时和事件循环阻塞。
        """
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        task_id = os.urandom(8).hex()

        # 1. 请求线程内完成文件落盘（UploadFile 句柄在响应后关闭）
        saved_files = []
        for i, f in enumerate(files):
            file_name = f.filename or f"upload-{i}"
            target = upload_dir / f"{task_id}-{i}-{file_name}"
            content = f.file.read()
            target.write_bytes(content)
            saved_files.append({
                "file_name": file_name,
                "file_path": str(target),
                "file_size": len(content),
                "file_index": i,
            })

        # 2. 记录任务状态
        with _task_lock:
            _import_tasks[task_id] = {
                "status": "processing",
                "total_files": len(saved_files),
                "processed_files": 0,
                "error": None,
            }

        # 3. 启动后台线程
        thread = threading.Thread(
            target=self._process_import_background,
            args=(task_id, saved_files, user_id),
            daemon=True,
        )
        thread.start()

        return {"task_id": task_id, "total_files": len(saved_files)}

    def _process_import_background(self, task_id: str, saved_files: list, user_id: int) -> None:
        """后台线程：解析文档 → 创建知识单元 → 批量向量化 → 写入 Milvus + ES 关键字索引。"""
        import logging
        logger = logging.getLogger(__name__)
        db = SessionLocal()
        try:
            pending_units: list[KnowledgeUnit] = []
            for sf in saved_files:
                file_name = sf["file_name"]
                file_path = sf["file_path"]
                file_size = sf["file_size"]
                saved = sf["file_index"]
                ext = Path(file_name).suffix.lower().lstrip(".")
                file_type = self._detect_file_type(ext)
                text = self.parse_document(file_path, file_type)
                chunks = self.split_text(text)
                project = self.extract_project_fields(text)
                financing = self.extract_financing_fields(text)
                for idx, chunk in enumerate(chunks):
                    unit = KnowledgeUnit(
                        unit_code=self.generate_unit_code(db),
                        title=Path(file_name).stem,
                        content=chunk,
                        summary=chunk[:200],
                        category=self._category_for(file_name),
                        source_file_name=file_name,
                        file_type=file_type,
                        file_size=file_size,
                        industry=project["fields"].get("industry"),
                        financing_round=project["fields"].get("financing_round"),
                        amount=project["fields"].get("amount"),
                        currency=project["fields"].get("currency"),
                        valuation=project["fields"].get("valuation"),
                        region=project["fields"].get("region"),
                        deal_stage=project["fields"].get("deal_stage"),
                        confidential_level=1,
                        status="active",
                        version=1,
                        creator_id=user_id,
                    )
                    db.add(unit)
                    db.flush()
                    pending_units.append(unit)
                # 更新已处理文件数
                with _task_lock:
                    if task_id in _import_tasks:
                        _import_tasks[task_id]["processed_files"] += 1
            # ---- 写入默认数据权限：confidential_level<=1 视为公开，全局可读；创建者本人始终可读 ----
            for unit in pending_units:
                if unit.confidential_level is not None and unit.confidential_level <= 1:
                    db.add(UnitPermission(unit_id=unit.id, target_type="global", target_id=0))
                db.add(UnitPermission(unit_id=unit.id, target_type="user", target_id=user_id))
            # ---- 先把知识单元持久化到数据库（不依赖向量索引，保证列表可见） ----
            db.commit()
            # 业务数据提交成功后即标记完成，前端进度到 100%
            with _task_lock:
                if task_id in _import_tasks:
                    _import_tasks[task_id]["status"] = "done"
            # ---- 再批量向量化写入 Milvus + ES 关键字索引（后处理，失败不影响已入库数据） ----
            if pending_units:
                try:
                    self._write_milvus_vectors(pending_units, task_id=task_id)
                except Exception:  # noqa: BLE001
                    # Milvus 向量化失败：数据库记录已持久化，不回滚，仅记录告警
                    logger.exception(
                        "任务 %s Milvus 向量写入失败：知识单元已入库，但向量检索可能缺失", task_id
                    )
                try:
                    self._write_keyword_index(pending_units)
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "任务 %s ES 关键字索引失败：知识单元已入库，但关键字检索可能缺失", task_id
                    )
        except Exception as e:
            logger.exception("导入任务 %s 失败", task_id)
            db.rollback()
            with _task_lock:
                if task_id in _import_tasks:
                    _import_tasks[task_id]["status"] = "error"
                    _import_tasks[task_id]["error"] = str(e)
        finally:
            db.close()

    def get_import_status(self, task_id: str) -> dict:
        """查询导入任务状态（内存级）。"""
        with _task_lock:
            return dict(_import_tasks.get(task_id, {}))

    def parse_document(self, file_path: str, file_type: str) -> str:
        """解析 PDF / Markdown / Word / TXT 格式文档，返回纯文本。"""
        parser = _PARSERS[file_type]
        return parser(file_path)

    def split_text(self, text: str, unit_max_len: int = 500) -> list[str]:
        """将项目文档内容拆分为独立知识单元。"""
        return split_text(text, max_length=unit_max_len, overlap=50)

    def extract_project_fields(self, text: str) -> dict:
        """抽取项目名称、行业赛道、融资轮次、金额、币种、估值、地区、风险点等业务字段。"""
        fields, warnings, spans = {}, [], []
        project_name = self._find_first(r"项目[：:]\s*([^\n，。 ]{2,30})", text)
        if project_name:
            fields["project_name"] = project_name
            spans.append({"field": "project_name", "value": project_name})
        else:
            warnings.append("缺少 project_name")
        industry_raw = self._find_first(r"行业[：:]\s*([^\n，。 ]{2,30})", text)
        industry = self.normalize_industry(industry_raw) if industry_raw else None
        if industry:
            fields["industry"] = industry
            spans.append({"field": "industry", "value": industry_raw})
        round_raw = self._find_first(r"轮次[：:]\s*([^\n，。 ]{2,30})", text)
        round_norm = self.normalize_round(round_raw) if round_raw else None
        if round_norm:
            fields["financing_round"] = round_norm
            spans.append({"field": "financing_round", "value": round_raw})
        amount_match = self._find_amount(text)
        if amount_match:
            fields.update(amount_match)
            spans.append({"field": "amount", "value": amount_match})
        region = self._find_first(r"地区[：:]\s*([^\n，。 ]{2,30})", text)
        if region:
            fields["region"] = region
            spans.append({"field": "region", "value": region})
        stage_raw = self._find_first(r"阶段[：:]\s*([^\n，。 ]{2,30})", text)
        stage = self.normalize_stage(stage_raw) if stage_raw else None
        if stage:
            fields["deal_stage"] = stage
            spans.append({"field": "deal_stage", "value": stage_raw})
        risk_points = re.findall(r"风险点[：:]\s*([^\n。]+)", text)
        if risk_points:
            fields["risk_points"] = [r.strip() for r in risk_points]
            spans.append({"field": "risk_points", "value": risk_points})
        parties = re.findall(r"相关方[：:]\s*([^\n。]+)", text)
        if parties:
            fields["related_parties"] = [p.strip() for p in parties]
            spans.append({"field": "related_parties", "value": parties})
        validated = self.validate_extracted_fields(fields)
        warnings.extend(validated["warnings"])
        errors = validated["errors"]
        return {
            "fields": fields,
            "confidence": self._confidence(fields, errors),
            "warnings": warnings,
            "source_spans": spans,
        }

    def extract_financing_fields(self, text: str) -> dict:
        """抽取融资需求、资金方偏好、行业方向、金额区间与融资阶段等字段。"""
        fields, spans = {}, []
        need = self._find_first(r"融资需求[：:]\s*([^\n。]+)", text)
        if need:
            fields["financing_need_type"] = self._first_token(need)
            spans.append({"field": "financing_need_type", "value": need})
        target_industry = re.findall(r"目标行业[：:]\s*([^\n。]+)", text)
        if target_industry:
            fields["target_industry"] = [self.normalize_industry(t) or t for t in target_industry]
            spans.append({"field": "target_industry", "value": target_industry})
        amount_min = self._find_amount(text)
        amount_max = self._find_amount(text, group_index=1)
        if amount_min and amount_max:
            fields["amount_range"] = {
                "min": amount_min["amount"],
                "max": amount_max["amount"],
                "currency": amount_min.get("currency", "CNY"),
            }
            spans.append({"field": "amount_range", "value": fields["amount_range"]})
        expected_round = self._find_first(r"期望轮次[：:]\s*([^\n。]+)", text)
        if expected_round:
            fields["expected_round"] = self.normalize_round(expected_round) or expected_round
            spans.append({"field": "expected_round", "value": expected_round})
        investor_pref = re.findall(r"偏好[：:]\s*([^\n。]+)", text)
        if investor_pref:
            fields["investor_preference"] = [p.strip() for p in investor_pref]
            spans.append({"field": "investor_preference", "value": investor_pref})
        region = self._find_first(r"地区[：:]\s*([^\n。]+)", text)
        if region:
            fields["region"] = region
            spans.append({"field": "region", "value": region})
        contact = self._find_first(r"联系方式[：:]\s*([^\n。]+)", text)
        if contact:
            fields["contact_scope"] = contact
            spans.append({"field": "contact_scope", "value": contact})
        return {
            "fields": fields,
            "confidence": self._confidence(fields, []),
            "warnings": [],
            "source_spans": spans,
        }

    def sync_vector_index(self, unit: KnowledgeUnit) -> None:
        """将投融资知识单元向量化并写入 Milvus 向量索引，同步 ES 关键字索引。

        Milvus 为必需主索引，写入失败向上抛出（由调用方置 index_status=failed）；
        ES 为辅助关键字索引，失败仅告警，不影响向量检索（可独立 rebuild 补齐）。
        """
        import logging

        logger = logging.getLogger(__name__)
        ensure_knowledge_collection()
        text = f"{unit.title}\n{unit.summary or ''}\n{unit.content or ''}"
        vector = embed_text(text)
        metadata = self._unit_metadata(unit)
        index_unit(unit.unit_code, vector, metadata)
        flush_knowledge_collection()
        ensure_knowledge_index()
        try:
            index_keyword_unit(unit.unit_code, metadata)
        except Exception:  # noqa: BLE001
            logger.exception("ES 关键字索引写入失败（不影响 Milvus 向量检索，可独立 rebuild 补齐）")

    def _unit_metadata(self, unit: KnowledgeUnit) -> dict:
        """知识单元 → 索引元数据（Milvus 标量字段 / ES 关键字字段共用）。"""
        return {
            "title": unit.title,
            "content": unit.content,
            "summary": unit.summary,
            "industry": unit.industry,
            "financing_round": unit.financing_round,
            "deal_stage": unit.deal_stage,
            "confidential_level": unit.confidential_level,
            "status": unit.status,
        }

    def _write_milvus_vectors(
        self,
        units: list[KnowledgeUnit],
        batch_size: int = 32,
        task_id: str | None = None,
    ) -> int:
        """批量向量化并写入 Milvus 向量集合，返回写入条数。

        按批 embedding → upsert → flush，保证导入/重建后立即可检索。
        """
        import logging

        logger = logging.getLogger(__name__)
        ensure_knowledge_collection()
        total = len(units)
        written = 0
        for i in range(0, total, batch_size):
            batch = units[i : i + batch_size]
            texts = [
                f"{u.title}\n{u.summary or ''}\n{u.content or ''}" for u in batch
            ]
            vectors = embed_batch(texts)
            for unit, vec in zip(batch, vectors):
                index_unit(unit.unit_code, vec, self._unit_metadata(unit))
            flush_knowledge_collection()
            written += len(batch)
            logger.info(
                "向量化进度：%d/%d%s", written, total,
                f"（任务 {task_id}）" if task_id else "",
            )
        logger.info("向量化完成，已写入 Milvus %d 条。", written)
        return written

    def _write_keyword_index(self, units: list[KnowledgeUnit], batch_size: int = 32) -> int:
        """批量写入 ES 关键字索引（BM25 检索），与向量索引解耦。"""
        ensure_knowledge_index()
        count = 0
        for i in range(0, len(units), batch_size):
            batch = units[i : i + batch_size]
            for unit in batch:
                index_keyword_unit(unit.unit_code, self._unit_metadata(unit))
            count += len(batch)
        return count

    def rebuild_vector_index(
        self,
        db: Session,
        status_filter: str | None = "active",
        batch_size: int = 32,
        on_progress=None,
        index_status_filter: str | None = None,
    ) -> dict:
        """重建知识单元向量索引（Milvus 向量 + ES 关键字），用于 Milvus 故障恢复 / 索引迁移 / 补齐缺失。

        过滤优先级：index_status_filter（pending/indexed/failed）优先；否则按 status_filter 过滤实体。
        逐条回写 index_status 与 vector_synced_at，使「failed 兜底 + 可增量重试」闭环；
        ES 关键字索引仅对向量化成功的单元重建，失败仅告警；单条失败不影响整体，返回统计。
        """
        import logging
        from datetime import datetime

        logger = logging.getLogger(__name__)
        stmt = select(KnowledgeUnit)
        if index_status_filter:
            stmt = stmt.where(KnowledgeUnit.index_status == index_status_filter)
        elif status_filter:
            stmt = stmt.where(KnowledgeUnit.status == status_filter)
        units = db.execute(stmt).scalars().all()
        total = len(units)
        indexed = 0
        failed: list[int] = []
        indexed_units: list[KnowledgeUnit] = []
        try:
            ensure_knowledge_collection()
        except Exception:  # noqa: BLE001
            logger.exception("Milvus 不可用，无法重建向量索引")
            return {"total": total, "indexed": 0, "failed": [u.id for u in units]}
        for i in range(0, total, batch_size):
            batch = units[i : i + batch_size]
            texts = [f"{u.title}\n{u.summary or ''}\n{u.content or ''}" for u in batch]
            try:
                vectors = embed_batch(texts)
            except Exception:  # noqa: BLE001
                logger.exception("rebuild_vector_index 批量向量化失败（批次 %d）", i)
                for u in batch:
                    u.index_status = "failed"
                failed.extend(u.id for u in batch)
                db.commit()  # 持久化本批次 failed 状态
                if on_progress:
                    on_progress(min(i + batch_size, total), total)
                continue
            for unit, vec in zip(batch, vectors):
                try:
                    index_unit(unit.unit_code, vec, self._unit_metadata(unit))
                    indexed += 1
                    unit.index_status = "indexed"
                    unit.vector_synced_at = datetime.utcnow()
                    indexed_units.append(unit)
                except Exception:  # noqa: BLE001
                    logger.exception("rebuild_vector_index 写入 Milvus 失败 unit=%s", unit.id)
                    unit.index_status = "failed"
                    failed.append(unit.id)
            db.commit()  # 持久化本批次 indexed/failed 状态
            try:
                flush_knowledge_collection()
            except Exception:  # noqa: BLE001
                logger.exception("rebuild_vector_index flush 失败（批次 %d）", i)
            if on_progress:
                on_progress(min(i + batch_size, total), total)
        # ES 关键字索引（BM25），仅对向量化成功的单元重建；失败仅告警
        try:
            self._write_keyword_index(indexed_units, batch_size)
        except Exception:  # noqa: BLE001
            logger.exception("rebuild_vector_index 写 ES 关键字索引失败（不影响向量检索）")
        db.commit()  # 最终持久化索引状态
        return {"total": total, "indexed": indexed, "failed": failed}

    def trigger_reindex(
        self,
        status_filter: str | None = "active",
        batch_size: int = 32,
        index_status_filter: str | None = None,
    ) -> str:
        """后台异步触发向量索引重建（Milvus + ES 关键字），返回 task_id（用于前端/运维轮询）。"""
        task_id = os.urandom(8).hex()
        with _task_lock:
            _reindex_tasks[task_id] = {
                "status": "processing",
                "total": 0,
                "indexed": 0,
                "failed": 0,
                "error": None,
            }
        thread = threading.Thread(
            target=self._reindex_background,
            args=(task_id, status_filter, batch_size, index_status_filter),
            daemon=True,
        )
        thread.start()
        return task_id

    def _reindex_background(
        self,
        task_id: str,
        status_filter: str | None,
        batch_size: int,
        index_status_filter: str | None = None,
    ) -> None:
        """后台线程：重建向量索引（Milvus + ES 关键字）并更新任务状态。"""
        import logging

        logger = logging.getLogger(__name__)
        db = SessionLocal()
        try:
            def on_progress(done: int, total: int) -> None:
                with _task_lock:
                    if task_id in _reindex_tasks:
                        _reindex_tasks[task_id]["total"] = total
                        _reindex_tasks[task_id]["indexed"] = done

            result = self.rebuild_vector_index(
                db,
                status_filter,
                batch_size,
                on_progress,
                index_status_filter,
            )
            with _task_lock:
                if task_id in _reindex_tasks:
                    _reindex_tasks[task_id].update(
                        {
                            "status": "done",
                            "total": result["total"],
                            "indexed": result["indexed"],
                            "failed": len(result["failed"]),
                        }
                    )
        except Exception as e:  # noqa: BLE001
            logger.exception("reindex 任务 %s 失败", task_id)
            with _task_lock:
                if task_id in _reindex_tasks:
                    _reindex_tasks[task_id]["status"] = "error"
                    _reindex_tasks[task_id]["error"] = str(e)
        finally:
            db.close()

    def get_reindex_status(self, task_id: str) -> dict:
        """查询向量索引重建任务状态（内存级）。"""
        with _task_lock:
            return dict(_reindex_tasks.get(task_id, {}))

    def manage_unit_version_status(
        self,
        db: Session,
        unit_id: int,
        version: int | None = None,
        status: str | None = None,
        confidential_level: int | None = None,
    ) -> None:
        """维护知识单元版本、状态与保密级别。"""
        unit = db.get(KnowledgeUnit, unit_id)
        if version is not None:
            unit.version = version
        if status is not None:
            unit.status = status
        if confidential_level is not None:
            unit.confidential_level = confidential_level
        db.commit()

    def list_units(self, db: Session, query: dict) -> dict:
        """GET /api/knowledge/units：按行业、轮次、项目阶段、保密级别、状态分页查询。"""
        stmt = select(KnowledgeUnit)
        conditions = []
        for key in ("industry", "financing_round", "deal_stage", "status"):
            if query.get(key):
                conditions.append(getattr(KnowledgeUnit, key) == query[key])
        if query.get("confidential_level"):
            conditions.append(KnowledgeUnit.confidential_level == query["confidential_level"])
        if conditions:
            stmt = stmt.where(*conditions)
        page = max(1, query.get("page", 1))
        page_size = max(1, min(200, query.get("page_size", 20)))
        stmt = stmt.order_by(KnowledgeUnit.updated_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = [self._serialize_list(u) for u in db.execute(stmt).scalars()]
        return {"items": items, "page": page, "page_size": page_size}

    def generate_unit_code(self, db: Session) -> str:
        """生成统一编号：年月日(YYYYMMDD) + 4 位当日序号，如 202608180001。

        序号取当日已存在同前缀编号的最大值 +1；并发极低（单后端顺序导入），
        依赖 unit_code 唯一约束兜底极端碰撞。
        """
        from datetime import date

        today = date.today().strftime("%Y%m%d")
        prefix = today
        max_code = db.execute(
            select(func.max(KnowledgeUnit.unit_code)).where(
                KnowledgeUnit.unit_code.like(f"{prefix}%")
            )
        ).scalar()
        seq = (int(max_code[len(prefix):]) + 1) if max_code else 1
        return f"{prefix}{seq:04d}"

    def create_unit(self, db: Session, data: dict, user_id: int) -> dict:
        """新建投融资知识单元（MySQL 先落库，向量索引后同步并回写状态）。"""
        import logging
        from datetime import datetime

        logger = logging.getLogger(__name__)

        unit = KnowledgeUnit(
            unit_code=data.get("unit_code") or self.generate_unit_code(db),
            title=data["title"],
            content=data.get("content", ""),
            summary=data.get("summary"),
            category=data.get("category"),
            industry=self.normalize_industry(data.get("industry")),
            financing_round=self.normalize_round(data.get("financing_round")),
            amount=data.get("amount"),
            currency=data.get("currency"),
            valuation=data.get("valuation"),
            region=data.get("region"),
            deal_stage=data.get("deal_stage"),
            confidential_level=data.get("confidential_level", 1),
            status=data.get("status", "active"),
            version=1,
            creator_id=user_id,
        )
        db.add(unit)
        db.flush()
        # 写入默认数据权限：confidential_level<=1 视为公开，全局可读；创建者本人始终可读
        if data.get("confidential_level", 1) <= 1:
            db.add(UnitPermission(unit_id=unit.id, target_type="global", target_id=0))
        db.add(UnitPermission(unit_id=unit.id, target_type="user", target_id=user_id))
        # 如果来源是知识缺口，标记缺口为已解决并关联新建单元
        gap_id = data.get("gap_id")
        if gap_id:
            from app.models.models import KnowledgeGap
            gap = db.get(KnowledgeGap, gap_id)
            if gap:
                gap.status = "resolved"
                gap.resolved_unit_id = unit.id
        db.commit()
        db.refresh(unit)
        try:
            self.sync_vector_index(unit)
            unit.index_status = "indexed"
            unit.vector_synced_at = datetime.utcnow()
            db.commit()
        except Exception:  # noqa: BLE001
            logger.exception(
                "新建知识单元 %s 向量索引同步失败（实体已入库），等待 reindex 兜底",
                unit.id,
            )
            unit.index_status = "failed"
            db.commit()
        return self._serialize_list(unit)

    def get_unit(self, db: Session, unit_id: int) -> dict:
        """GET /api/knowledge/units/{id}：查询知识单元详情与已配置的数据权限列表。"""
        unit = db.get(KnowledgeUnit, unit_id)
        perm_rows = db.execute(
            select(UnitPermission).where(UnitPermission.unit_id == unit_id)
        ).scalars()
        permissions = [
            {"target_type": p.target_type, "target_id": p.target_id} for p in perm_rows
        ]
        item = self._serialize_list(unit)
        return {
            **item,
            "content": unit.content,
            "summary": unit.summary,
            "category": unit.category,
            "permission_summary": permissions,
        }

    def update_unit(self, db: Session, unit_id: int, data: dict, user_id: int) -> dict:
        """PUT /api/knowledge/units/{id}：更新知识单元内容并递增版本（同步回写索引状态）。"""
        import logging
        from datetime import datetime

        logger = logging.getLogger(__name__)
        unit = db.get(KnowledgeUnit, unit_id)
        for k in (
            "title",
            "content",
            "summary",
            "category",
            "industry",
            "financing_round",
            "amount",
            "currency",
            "valuation",
            "region",
            "deal_stage",
            "confidential_level",
            "status",
        ):
            if k in data:
                setattr(unit, k, data[k])
        if "industry" in data:
            unit.industry = self.normalize_industry(data["industry"])
        if "financing_round" in data:
            unit.financing_round = self.normalize_round(data["financing_round"])
        # 同步保密级别与权限记录：公开(<=1) 自动加 global，私有(>1) 移除 global
        if "confidential_level" in data:
            new_cl = data["confidential_level"]
            existing_global = db.execute(
                select(UnitPermission).where(
                    UnitPermission.unit_id == unit_id, UnitPermission.target_type == "global"
                )
            ).scalars().first()
            if new_cl <= 1 and not existing_global:
                db.add(UnitPermission(unit_id=unit_id, target_type="global", target_id=0))
            elif new_cl > 1 and existing_global:
                db.delete(existing_global)
        unit.version += 1
        db.commit()
        try:
            self.sync_vector_index(unit)
            unit.index_status = "indexed"
            unit.vector_synced_at = datetime.utcnow()
            db.commit()
        except Exception:  # noqa: BLE001
            logger.exception(
                "更新知识单元 %s 向量索引同步失败（实体已更新），等待 reindex 兜底",
                unit.id,
            )
            unit.index_status = "failed"
            db.commit()
        return self._serialize_list(unit)

    def delete_units(self, db: Session, unit_ids: list[int]) -> int:
        """DELETE /api/knowledge/units：批量删除知识单元（含 Milvus / ES 索引与权限清理）。

        顺序：先删向量/关键字索引，再删 MySQL 实体（避免「MySQL 已删、索引残留」的反向缺口）；
        索引删除失败仅告警，不阻断实体删除（实体已删，索引残留可由全量 rebuild 清理）。
        """
        import logging

        logger = logging.getLogger(__name__)
        units = db.execute(
            select(KnowledgeUnit).where(KnowledgeUnit.id.in_(unit_ids))
        ).scalars()
        count = 0
        for unit in units:
            db.execute(
                UnitPermission.__table__.delete().where(
                    UnitPermission.unit_id == unit.id
                )
            )
            try:
                delete_unit_from_index(unit.unit_code)
                delete_keyword_unit(unit.unit_code)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "删除知识单元 %s 的向量/关键字索引失败（实体将继续删除，索引残留需 rebuild 清理）",
                    unit.id,
                )
            db.delete(unit)
            count += 1
        db.commit()
        return count

    # ----- 辅助方法（技能文档 01：抽取规则） -----
    def normalize_industry(self, text: str) -> str | None:
        """行业统一以中文命名：英文 code / 中文别名 → 中文规范名；未知值原样保留。"""
        if not text or not text.strip():
            return None
        key = text.strip()
        if key in _INDUSTRY_CANONICAL:
            return _INDUSTRY_CANONICAL[key]
        key_lower = key.lower()
        if key_lower in _INDUSTRY_CANONICAL:
            return _INDUSTRY_CANONICAL[key_lower]
        return key

    def normalize_round(self, text: str) -> str | None:
        s = text.strip().lower()
        for k, v in _ROUND_SYNONYMS.items():
            if k in s:
                return v
        if s in _ROUND_ENUM:
            return s
        return "other"

    def normalize_stage(self, text: str) -> str | None:
        s = text.strip().lower()
        for k, v in _STAGE_SYNONYMS.items():
            if k in s:
                return v
        if s in _STAGE_ENUM:
            return s
        return "sourcing"

    def parse_amount_currency(self, text: str) -> dict:
        m = _AMOUNT_RE.search(text)
        if not m:
            return {}
        amount = float(m.group("amount"))
        unit = m.group("unit")
        ccy_raw = (m.group("ccy") or "").upper()
        ccy_map = {"人民币": "CNY", "美元": "USD", "港币": "HKD", "港元": "HKD", "欧元": "EUR"}
        ccy = ccy_map.get(ccy_raw, ccy_raw or "CNY")
        if ccy not in _CURRENCY_ENUM:
            ccy = "other"
        if unit in _UNIT_MULT:
            amount *= _UNIT_MULT[unit]
        return {"amount": amount, "currency": ccy}

    def validate_extracted_fields(self, fields: dict) -> dict:
        errors: list[str] = []
        warnings: list[str] = []
        if "project_name" not in fields:
            errors.append("project_name 必填缺失")
        if fields.get("financing_round") and fields["financing_round"] not in _ROUND_ENUM:
            errors.append("financing_round 枚举非法")
        if fields.get("currency") and fields["currency"] not in _CURRENCY_ENUM:
            errors.append("currency 枚举非法")
        if fields.get("deal_stage") and fields["deal_stage"] not in _STAGE_ENUM:
            errors.append("deal_stage 枚举非法")
        rng = fields.get("amount_range")
        if isinstance(rng, dict) and rng.get("min") is not None and rng.get("max") is not None:
            if rng["min"] > rng["max"]:
                errors.append("amount_range min > max")
        return {"errors": errors, "warnings": warnings}

    # ----- 内部 -----
    def _detect_file_type(self, ext: str) -> str:
        mapping = {"pdf": "pdf", "md": "markdown", "markdown": "markdown", "docx": "word", "txt": "txt"}
        return mapping.get(ext, "txt")

    def _category_for(self, file_name: str) -> str:
        s = file_name.lower()
        if "尽调" in file_name or "due" in s:
            return "due_diligence"
        if "投决" in file_name or "ic" in s:
            return "investment_committee"
        if "协议" in file_name or "agreement" in s or "term" in s:
            return "agreement"
        if "投后" in file_name or "post" in s:
            return "post_investment"
        return "general"

    def _find_first(self, pattern: str, text: str) -> str | None:
        m = re.search(pattern, text)
        return m.group(1).strip() if m else None

    def _find_amount(self, text: str, group_index: int = 0) -> dict | None:
        matches = list(_AMOUNT_RE.finditer(text))
        if not matches or len(matches) <= group_index:
            return None
        m = matches[group_index]
        amount = float(m.group("amount"))
        unit = m.group("unit")
        ccy_raw = (m.group("ccy") or "").upper()
        ccy_map = {"人民币": "CNY", "美元": "USD", "港币": "HKD", "港元": "HKD", "欧元": "EUR"}
        ccy = ccy_map.get(ccy_raw, ccy_raw or "CNY")
        if ccy not in _CURRENCY_ENUM:
            ccy = "other"
        if unit in _UNIT_MULT:
            amount *= _UNIT_MULT[unit]
        return {"amount": amount, "currency": ccy}

    def _first_token(self, text: str) -> str:
        return text.strip().split()[0] if text else ""

    def _confidence(self, fields: dict, errors: list[str]) -> float:
        if errors:
            return 0.0
        return round(min(1.0, 0.3 + 0.1 * len(fields)), 2)

    def _serialize_list(self, unit: KnowledgeUnit) -> dict:
        return {
            "id": unit.id,
            "unit_code": unit.unit_code,
            "title": unit.title,
            "industry": unit.industry,
            "financing_round": unit.financing_round,
            "deal_stage": unit.deal_stage,
            "confidential_level": unit.confidential_level,
            "creator_id": unit.creator_id,
            "status": unit.status,
            "created_at": unit.created_at,
            "updated_at": unit.updated_at,
            "permission_summary": [],  # 列表级仅占位，详情接口返回完整权限
        }


knowledge_service = KnowledgeService()