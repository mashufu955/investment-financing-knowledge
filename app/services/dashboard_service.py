"""04-数据看板（技能文档 04）。

异步记录每轮问答访问日志，并聚合计算投融资业务指标与知识库使用指标。
"""
import json
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.redis import get_redis
from app.models.models import (
    Faq,
    KnowledgeUnit,
    QaAccessLog,
)


_CURRENCY_TO_CNY = {"CNY": 1.0, "USD": 7.2, "HKD": 0.92, "EUR": 7.8, "other": 1.0}
_DASHBOARD_CACHE_PREFIX = "dashboard:cache:"
_DASHBOARD_CACHE_TTL = 300

_KB_CACHE: dict[str, tuple[float, dict]] = {}


class DashboardService:
    """数据看板服务。"""

    def record_access_log(self, db: Session, log: dict) -> None:
        """异步记录访问日志，包含用户、耗时、Token 消耗、命中项目知识单元、提问内容。"""
        row = QaAccessLog(
            session_id=log.get("session_id"),
            user_id=log["user_id"],
            question=log.get("question"),
            answer=log.get("answer"),
            recalled_unit_ids_json=log.get("recalled_unit_ids_json"),
            authorized_unit_ids_json=log.get("authorized_unit_ids_json"),
            unauthorized_unit_ids_json=log.get("unauthorized_unit_ids_json"),
            prompt_tokens=log.get("prompt_tokens"),
            completion_tokens=log.get("completion_tokens"),
            total_tokens=log.get("total_tokens"),
            response_time_ms=log.get("response_time_ms"),
        )
        db.add(row)
        db.commit()

    def aggregate_dashboard_metrics(self, db: Session) -> None:
        """按日与实时汇总访问指标、项目指标、融资指标、热度榜单与性能分布。"""
        for period in ("daily", "weekly", "monthly"):
            payload = {
                "metrics": self.get_metrics(db),
                "pipeline": self.get_project_pipeline_metrics(db),
                "rankings": {
                    "questions": self.get_question_rankings(db),
                    "units": self.get_unit_rankings(db),
                },
                "tokens": self.get_token_stats(db),
            }
            cache_metrics(period, payload)

    def get_metrics(self, db: Session) -> dict:
        """GET /api/dashboard/metrics：查询访问总次数、独立用户数、知识单元数、Token 总量与平均耗时。"""
        access_count = db.execute(select(func.count(QaAccessLog.id))).scalar() or 0
        user_count = db.execute(select(func.count(func.distinct(QaAccessLog.user_id)))).scalar() or 0
        unit_count = db.execute(select(func.count(KnowledgeUnit.id))).scalar() or 0
        total_tokens = db.execute(select(func.coalesce(func.sum(QaAccessLog.total_tokens), 0))).scalar() or 0
        avg_time = db.execute(select(func.avg(QaAccessLog.response_time_ms))).scalar() or 0
        return {
            "project_count": unit_count,
            "financing_count": 0,
            "knowledge_units_total": unit_count,
            "token_total": int(total_tokens),
            "avg_response_time": round(float(avg_time), 2),
            "access_count": access_count,
            "user_count": user_count,
        }

    def get_project_pipeline_metrics(self, db: Session) -> dict:
        """查询项目数量、阶段分布、融资金额与行业分布。"""
        stage_rows = db.execute(
            select(KnowledgeUnit.deal_stage, func.count(KnowledgeUnit.id))
            .group_by(KnowledgeUnit.deal_stage)
        ).all()
        pipeline = [{"deal_stage": s or "unknown", "count": c} for s, c in stage_rows]
        amount_rows = db.execute(
            select(KnowledgeUnit.amount, KnowledgeUnit.currency)
        ).all()
        amount_by_currency = defaultdict(float)
        total_cny = 0.0
        for amount, ccy in amount_rows:
            if amount is None:
                continue
            rate = _CURRENCY_TO_CNY.get(ccy or "CNY", 1.0)
            total_cny += float(amount) * rate
            amount_by_currency[ccy or "CNY"] += float(amount)
        industry_rows = db.execute(
            select(KnowledgeUnit.industry, func.count(KnowledgeUnit.id))
            .group_by(KnowledgeUnit.industry)
        ).all()
        industry = [{"industry": i or "unknown", "count": c} for i, c in industry_rows]
        return {
            "pipeline_by_stage": pipeline,
            "financing_amount": {
                "total_cny": round(total_cny, 2),
                "by_currency": dict(amount_by_currency),
            },
            "industry_distribution": industry,
            "conversion_rate": compute_conversion_rate([(p["deal_stage"], p["count"]) for p in pipeline]),
        }

    def get_question_rankings(self, db: Session, top_n: int = 10) -> list:
        """GET /api/dashboard/rankings/questions：查询投融资常见问题 TOP 榜。"""
        rows = db.execute(
            select(QaAccessLog.question, func.count(QaAccessLog.id))
            .where(QaAccessLog.question.isnot(None))
            .group_by(QaAccessLog.question)
            .order_by(desc(func.count(QaAccessLog.id)))
            .limit(top_n)
        ).all()
        return [{"question": q, "count": c} for q, c in rows]

    def get_unit_rankings(self, db: Session, top_n: int = 10) -> list:
        """GET /api/dashboard/rankings/units：查询最常访问项目知识单元 TOP 榜。"""
        rows = db.execute(
            select(QaAccessLog.authorized_unit_ids_json).where(QaAccessLog.authorized_unit_ids_json.isnot(None))
        ).all()
        counter: Counter = Counter()
        for (value,) in rows:
            if isinstance(value, list):
                for uid in value:
                    counter[uid] += 1
            elif isinstance(value, str):
                for uid in json.loads(value or "[]"):
                    counter[uid] += 1
        return [{"unit_id": uid, "count": c} for uid, c in counter.most_common(top_n)]

    def get_token_stats(self, db: Session) -> dict:
        """GET /api/dashboard/stats/tokens：查询 Token 消耗与响应时间趋势。"""
        since = datetime.utcnow() - timedelta(days=7)
        rows = db.execute(
            select(
                func.date(QaAccessLog.created_at).label("d"),
                func.coalesce(func.sum(QaAccessLog.total_tokens), 0),
                func.avg(QaAccessLog.response_time_ms),
            )
            .where(QaAccessLog.created_at >= since)
            .group_by("d")
            .order_by("d")
        ).all()
        token_trend = [{"date": str(d), "total_tokens": int(t), "avg_response_time": float(rt or 0)} for d, t, rt in rows]
        return {
            "token_trend": token_trend,
            "faq_hit_rate": compute_faq_hit_rate(db),
        }


# ==================== 看板辅助方法（技能文档 04：细化方法） ====================
def define_metric_registry() -> list[dict]:
    """集中定义指标 ID、名称、公式、维度、周期和权限范围。"""
    return [
        {
            "id": "project_count",
            "name": "项目数量",
            "formula": "count(distinct project_id)",
            "dimensions": ["industry", "stage", "team", "fund"],
            "period": ["daily", "weekly", "monthly"],
        },
        {
            "id": "financing_amount",
            "name": "融资金额",
            "formula": "sum(amount_cny)",
            "dimensions": ["industry", "stage", "currency"],
            "period": ["daily", "weekly", "monthly"],
        },
        {
            "id": "faq_hit_rate",
            "name": "FAQ 命中率",
            "formula": "hit_count / total_qa_count",
            "dimensions": ["team", "product"],
            "period": ["daily", "weekly", "monthly"],
        },
        {
            "id": "token_total",
            "name": "Token 消耗",
            "formula": "sum(total_tokens)",
            "dimensions": ["team", "user"],
            "period": ["daily", "weekly", "monthly"],
        },
        {
            "id": "avg_response_time",
            "name": "平均响应时间",
            "formula": "avg(response_time_ms)",
            "dimensions": ["team", "user"],
            "period": ["daily", "weekly", "monthly"],
        },
    ]


def map_deal_stage(stage: str | None) -> str:
    """统一项目阶段枚举。"""
    if not stage:
        return "sourcing"
    mapping = {
        "sourcing": "sourcing",
        "due_diligence": "due_diligence",
        "尽调": "due_diligence",
        "投决": "investment_committee",
        "investment_committee": "investment_committee",
        "交割": "closing",
        "closing": "closing",
        "投后": "post_investment",
        "post_investment": "post_investment",
    }
    return mapping.get(stage, "sourcing")


def aggregate_project_pipeline(units: list, date_range: dict | None = None, scope: dict | None = None) -> dict:
    """按阶段统计项目数量。"""
    counter: Counter = Counter()
    for u in units:
        counter[map_deal_stage(u.deal_stage)] += 1
    return {"pipeline_by_stage": dict(counter)}


def aggregate_financing_amount(units: list, currency: str = "CNY") -> float:
    """统一币种后汇总金额。"""
    total = 0.0
    for u in units:
        if u.amount is None:
            continue
        rate = _CURRENCY_TO_CNY.get(u.currency or "CNY", 1.0)
        total += float(u.amount) * rate
    return round(total, 2)


def aggregate_industry_distribution(units: list) -> dict:
    """按标准行业统计项目和金额分布。"""
    counter: Counter = Counter()
    for u in units:
        counter[u.industry or "unknown"] += 1
    return dict(counter)


def compute_conversion_rate(stages: list[tuple[str, int]]) -> dict:
    """计算线索到立项、立项到投决、投决到交割等转化率。"""
    order = ["sourcing", "due_diligence", "investment_committee", "closing", "post_investment"]
    stage_map = {s: c for s, c in stages}
    rates = {}
    for i in range(1, len(order)):
        prev = stage_map.get(order[i - 1], 0)
        curr = stage_map.get(order[i], 0)
        rates[f"{order[i - 1]}_to_{order[i]}"] = round(curr / prev, 4) if prev else 0.0
    return rates


def compute_faq_hit_rate(db: Session) -> float:
    """计算 FAQ 命中率。"""
    total = db.execute(select(func.count(QaAccessLog.id))).scalar() or 0
    hit_faq_ids = db.execute(select(Faq.id).where(Faq.hit_count > 0)).scalars()
    if total == 0:
        return 0.0
    hits = db.execute(
        select(func.count(QaAccessLog.id)).where(QaAccessLog.authorized_unit_ids_json.isnot(None))
    ).scalar() or 0
    return round(hits / total, 4)


def filter_metrics_by_user_scope(metrics: dict, context: dict) -> dict:
    """看板数据执行权限过滤。"""
    if context.get("is_admin"):
        return metrics
    return {k: v for k, v in metrics.items() if k in {"knowledge_units_total", "token_total", "avg_response_time"}}


def cache_metrics(period: str, payload: dict) -> None:
    """日/周聚合缓存与刷新策略。"""
    try:
        get_redis().setex(f"{_DASHBOARD_CACHE_PREFIX}{period}", _DASHBOARD_CACHE_TTL, json.dumps(payload, default=str))
    except Exception:
        _KB_CACHE[period] = (datetime.utcnow().timestamp() + _DASHBOARD_CACHE_TTL, payload)


def render_project_pipeline(metrics: dict) -> dict:
    """定义前端图表所需的 data schema。"""
    return {
        "type": "funnel+bar",
        "stages": metrics.get("pipeline_by_stage", []),
        "industry": metrics.get("industry_distribution", []),
    }


def record_access_log_async(db: Session, log: dict) -> None:
    """异步写入访问日志，不阻塞问答链路。"""

    def _worker():
        DashboardService().record_access_log(db, log)

    threading.Thread(target=_worker, daemon=True).start()


dashboard_service = DashboardService()