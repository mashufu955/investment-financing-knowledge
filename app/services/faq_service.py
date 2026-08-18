"""05-知识沉淀与FAQ缓存（技能文档 05）。

覆盖投融资高频问题挖掘、FAQ 审核发布、问答缓存加速、
知识缺口识别与未命中问题分析。
"""
import json
import re
from collections import Counter
from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.redis import get_redis
from app.models.models import (
    Faq,
    KnowledgeGap,
    KnowledgeUnit,
    QaAccessLog,
)


_FAQ_TTL = 24 * 3600
_FAQ_PREFIX = "faq:"
_FAQ_VERSION_SUFFIX = ":version"

_EXACT_THRESHOLD = 0.98
_SEMANTIC_THRESHOLD = 0.85

_MINING_THRESHOLD = 3
_GAP_TOP_K = 20


class FaqService:
    """知识沉淀与 FAQ 服务。"""

    def mine_faq_recommendations(self, db: Session) -> list:
        """对历史提问进行语义去重与频次聚合，达到阈值后自动生成投融资 FAQ 推荐项。"""
        rows = db.execute(
            select(QaAccessLog.question, func.count(QaAccessLog.id).label("c"))
            .where(QaAccessLog.question.isnot(None))
            .group_by(QaAccessLog.question)
            .order_by(desc("c"))
        ).all()
        recommendations: list[dict] = []
        for question, count in rows:
            if count < _MINING_THRESHOLD:
                continue
            cluster = cluster_similar_questions([q for q, _ in rows if q], _SEMANTIC_THRESHOLD)
            for cluster_questions in cluster:
                if question in cluster_questions:
                    candidate = generate_faq_candidate({"questions": cluster_questions, "count": count})
                    if not self._existing_pending(db, candidate["question"]):
                        faq = Faq(
                            question=candidate["question"],
                            answer=candidate["answer"],
                            category=candidate["category"],
                            related_unit_id=candidate["related_unit_id"],
                            source_type="auto_mined",
                            status="pending_review",
                            hit_count=count,
                        )
                        db.add(faq)
                        db.flush()
                        recommendations.append(self._serialize(faq))
        db.commit()
        # 返回全部待审核 FAQ（不仅本次新挖掘），保证审核页始终有可操作项
        pending = db.execute(
            select(Faq).where(Faq.status == "pending_review").order_by(desc(Faq.hit_count))
        ).scalars()
        return [self._serialize(f) for f in pending]

    def identify_knowledge_gaps(self, db: Session) -> list:
        """识别召回相似度低于阈值或无可用项目知识支撑的问答记录，生成知识缺口项。"""
        rows = db.execute(
            select(QaAccessLog.question, func.count(QaAccessLog.id).label("c"), func.max(QaAccessLog.created_at))
            .where(QaAccessLog.question.isnot(None))
            .group_by(QaAccessLog.question)
            .order_by(desc("c"))
            .limit(_GAP_TOP_K)
        ).all()
        new_gaps: list[KnowledgeGap] = []
        for question, count, last_asked in rows:
            pattern = normalize_question(question)
            if not self._has_gap(db, pattern):
                gap = KnowledgeGap(
                    question_pattern=pattern,
                    sample_questions_json=[question],
                    ask_count=count,
                    last_asked_at=last_asked,
                    status="unresolved",
                )
                db.add(gap)
                db.flush()
                new_gaps.append(gap)
        db.commit()
        # 返回全部未解决缺口（不仅本次新挖掘），保证缺口页始终有可操作项
        existing = db.execute(
            select(KnowledgeGap).where(KnowledgeGap.status != "resolved")
        ).scalars()
        return merge_duplicate_gaps(list(existing))

    def review_faq(
        self,
        db: Session,
        faq_id: int,
        action: str,
        edited_answer: str | None,
        reviewer_id: int,
    ) -> dict:
        """POST /api/settlement/faqs/{id}/review：审核 FAQ。"""
        faq = db.get(Faq, faq_id)
        if action == "approve":
            if edited_answer:
                faq.answer = edited_answer
            faq.status = "published"
            faq.reviewer_id = reviewer_id
            faq.reviewed_at = datetime.utcnow()
            self.publish_faq(db, faq_id)
        elif action == "reject":
            faq.status = "rejected"
            faq.reviewer_id = reviewer_id
            faq.reviewed_at = datetime.utcnow()
            invalidate_faq_cache(faq_id, reason="rejected")
        db.commit()
        return self._serialize(faq)

    def publish_faq(self, db: Session, faq_id: int) -> None:
        """审核通过后标记为 published 并写入高速缓存。"""
        faq = db.get(Faq, faq_id)
        version = version_faq(faq_id)
        payload = {
            "faq_id": faq.id,
            "question": faq.question,
            "answer": faq.answer,
            "category": faq.category,
            "related_unit_id": faq.related_unit_id,
            "source_type": faq.source_type,
            "published_at": datetime.utcnow().isoformat(),
            "version": version,
        }
        try:
            get_redis().setex(f"{_FAQ_PREFIX}{faq_id}{_FAQ_VERSION_SUFFIX}{version}", _FAQ_TTL, json.dumps(payload))
            get_redis().set(f"{_FAQ_PREFIX}{faq_id}:active_version", version)
        except Exception:
            pass

    def list_published_faqs(self, db: Session) -> list:
        """展示已发布 FAQ 库及缓存生效状态。"""
        rows = db.execute(select(Faq).where(Faq.status == "published")).scalars()
        items = []
        for faq in rows:
            cache_status = self._cache_status(faq.id)
            items.append({**self._serialize(faq), "cache_status": cache_status})
        return items

    def update_faq_cache_status(self, db: Session, faq_id: int, cache_status: str) -> None:
        """更新已发布 FAQ 的缓存生效状态。"""
        invalidate_faq_cache(faq_id, reason=cache_status)

    def match_faq_cache(self, db: Session, question: str) -> str | None:
        """提供 FAQ 精确或语义相似度匹配与快速应答缓存，命中时直接输出标准答案。"""
        normalized = normalize_question(question)
        rows = db.execute(select(Faq).where(Faq.status == "published")).scalars()
        for faq in rows:
            score = _similarity(normalized, normalize_question(faq.question))
            if score >= _EXACT_THRESHOLD:
                trace_faq_hit(faq.id, question)
                return faq.answer
        candidates = [(faq, _similarity(normalized, normalize_question(faq.question))) for faq in rows]
        candidates.sort(key=lambda x: x[1], reverse=True)
        if candidates and candidates[0][1] >= _SEMANTIC_THRESHOLD:
            faq, score = candidates[0]
            trace_faq_hit(faq.id, question)
            return faq.answer
        return None

    # ----------- 内部 -----------
    def _serialize(self, faq: Faq) -> dict:
        return {
            "id": faq.id,
            "question": faq.question,
            "answer": faq.answer,
            "category": faq.category,
            "related_unit_id": faq.related_unit_id,
            "source_type": faq.source_type,
            "status": faq.status,
            "hit_count": faq.hit_count,
            "reviewer_id": faq.reviewer_id,
            "reviewed_at": faq.reviewed_at,
            "created_at": faq.created_at,
            "updated_at": faq.updated_at,
        }

    def _existing_pending(self, db: Session, question: str) -> bool:
        return bool(
            db.execute(
                select(Faq.id)
                .where(Faq.question == question, Faq.status == "pending_review")
                .limit(1)
            ).scalar()
        )

    def _has_gap(self, db: Session, pattern: str) -> bool:
        return bool(
            db.execute(
                select(KnowledgeGap.id)
                .where(KnowledgeGap.question_pattern == pattern, KnowledgeGap.status != "resolved")
                .limit(1)
            ).scalar()
        )

    def _cache_status(self, faq_id: int) -> str:
        try:
            r = get_redis()
            if r.exists(f"{_FAQ_PREFIX}{faq_id}:active_version"):
                return "active"
            return "miss"
        except Exception:
            return "unknown"


# ==================== 缓存 & 匹配辅助方法（技能文档 05：细化方法） ====================
def normalize_question(text: str) -> str:
    """统一大小写、标点、同义词与实体替换。"""
    if not text:
        return ""
    s = re.sub(r"[\s　]+", " ", text).strip().lower()
    s = re.sub(r"[？?！!，,。.\；;：:]", "", s)
    syn = {
        "融资需求": "融资",
        "投融资": "融资",
        "项目尽调": "尽调",
        "股权融资": "股权",
        "债券融资": "债券",
    }
    for k, v in syn.items():
        s = s.replace(k, v)
    return s


def cluster_similar_questions(questions: list[str], threshold: float) -> list[list[str]]:
    """按语义相似度聚类。"""
    clusters: list[list[str]] = []
    for q in questions:
        placed = False
        for cluster in clusters:
            rep = cluster[0]
            if _similarity(normalize_question(q), normalize_question(rep)) >= threshold:
                cluster.append(q)
                placed = True
                break
        if not placed:
            clusters.append([q])
    return clusters


def compute_frequency_threshold(logs: list[dict]) -> int:
    """定义自动推荐 FAQ 的频次阈值。"""
    counts = Counter(l.get("question", "") for l in logs)
    if not counts:
        return 3
    return max(3, int(sum(counts.values()) / max(1, len(counts))))


def generate_faq_candidate(cluster: dict) -> dict:
    """生成问题、建议答案、关联知识单元、推荐频次。"""
    questions = cluster.get("questions", [])
    return {
        "question": questions[0] if questions else "",
        "answer": "（自动生成）" + "；".join(q for q in questions[:3]),
        "category": "general",
        "related_unit_id": None,
        "frequency": cluster.get("count", 0),
    }


def merge_duplicate_gaps(gaps: list[KnowledgeGap]) -> list[dict]:
    """合并相似知识缺口，避免重复。"""
    seen: dict[str, dict] = {}
    out: list[dict] = []
    for g in gaps:
        key = g.question_pattern
        if key in seen:
            seen[key]["ask_count"] += g.ask_count
            continue
        seen[key] = {
            "id": g.id,
            "question_pattern": g.question_pattern,
            "ask_count": g.ask_count,
            "last_asked_at": g.last_asked_at,
            "status": g.status,
        }
    out.extend(seen.values())
    return out


def invalidate_faq_cache(faq_id: int, reason: str) -> None:
    """FAQ 修改或撤回时同步失效缓存。"""
    try:
        r = get_redis()
        keys = r.keys(f"{_FAQ_PREFIX}{faq_id}*")
        if keys:
            r.delete(*keys)
        r.set(f"{_FAQ_PREFIX}{faq_id}:invalidated_at", datetime.utcnow().isoformat())
    except Exception:
        return None


def version_faq(faq_id: int) -> int:
    """发布后保留版本，支持回滚。"""
    try:
        r = get_redis()
        v = int(r.get(f"{_FAQ_PREFIX}{faq_id}:active_version") or 0) + 1
        return v
    except Exception:
        return 1


def match_faq_cache(question: str, threshold: float) -> dict | None:
    """执行精确/语义匹配并返回命中结果。"""
    return _match_redis(question, threshold)


def trace_faq_hit(faq_id: int, question: str) -> None:
    """记录命中日志，用于后续命中率统计。"""
    try:
        r = get_redis()
        r.incr(f"{_FAQ_PREFIX}{faq_id}:hits")
    except Exception:
        return None


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    set_a, set_b = set(a), set(b)
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def _match_redis(question: str, threshold: float) -> dict | None:
    try:
        r = get_redis()
        for key in r.keys(f"{_FAQ_PREFIX}*"):
            if ":active_version" in key or ":hits" in key or ":invalidated_at" in key:
                continue
            payload = r.get(key)
            if not payload:
                continue
            data = json.loads(payload)
            score = _similarity(normalize_question(question), normalize_question(data.get("question", "")))
            if score >= threshold:
                return {"faq_id": data["faq_id"], "answer": data["answer"], "score": score}
    except Exception:
        return None
    return None


faq_service = FaqService()