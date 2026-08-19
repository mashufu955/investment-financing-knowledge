"""03-AI检索与问答鉴权（技能文档 03）。

覆盖会话管理、投融资知识召回、权限过滤、Prompt 组装、
流式回答生成与权限缺失提示。
"""
import json
import logging
import re
import time
import uuid
from typing import AsyncIterator

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.es import KNOWLEDGE_INDEX, ensure_knowledge_index, get_es_client
from app.core.milvus import search_units
from app.core.permissions import build_permission_context
from app.models.models import (
    KnowledgeUnit,
    QaAccessLog,
    QaMessage,
    QaSession,
    UnitPermission,
    User,
)
from app.services.dashboard_service import record_access_log_async
from app.services.org_service import org_service


_RECALL_TOP_K = 20
_FINAL_TOP_K = 5
_HYBRID_VECTOR_WEIGHT = 0.7
_HYBRID_KEYWORD_WEIGHT = 0.3
_TEMPERATURE = 0.1
_MAX_TOKENS = 2048

_SENSITIVE_KEYWORDS = (
    "投资建议",
    "未公开",
    "内部定价",
    "内幕",
    "个人信息",
    "身份证",
)

logger = logging.getLogger(__name__)


class AiQaService:
    """AI 检索与问答鉴权服务。"""

    def validate_login(self, db: Session, user_id: int) -> dict:
        """回答问题前校验用户登录态，获取用户所属团队、基金/项目范围与角色列表。"""
        user = db.get(User, user_id)
        if not user or user.status != 1:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录失效")
        return org_service.resolve_user_context(db, user_id)

    def manage_session(self, db: Session, user_id: int, session_id: str | None) -> dict:
        """管理问答会话与历史对话。"""
        if session_id:
            session = db.execute(
                select(QaSession).where(
                    QaSession.session_id == session_id, QaSession.user_id == user_id
                )
            ).scalar_one_or_none()
            if not session:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
            return {"session_id": session.session_id, "title": session.title}
        new_id = str(uuid.uuid4())
        session = QaSession(session_id=new_id, user_id=user_id, title=None)
        db.add(session)
        db.commit()
        return {"session_id": new_id, "title": None}

    def list_history_sessions(self, db: Session, user_id: int) -> list:
        """获取历史对话会话列表。"""
        rows = db.execute(
            select(QaSession)
            .where(QaSession.user_id == user_id)
            .order_by(QaSession.updated_at.desc())
        ).scalars()
        return [
            {"session_id": s.session_id, "title": s.title, "updated_at": s.updated_at}
            for s in rows
        ]

    def retrieve_candidates(
        self,
        db: Session,
        question: str,
        user_context: dict,
        filters: dict | None = None,
    ) -> list:
        """执行向量检索/关键字混合召回。

        向量链路（Milvus ANN）异常时整体降级为数据库关键字检索，
        保证问答流不因召回失败而中断。
        """
        try:
            vector_candidates = _vector_search(question)
            return _merge_with_keyword(question, vector_candidates)
        except Exception as exc:
            logger.warning("向量召回失败，降级为关键字检索: %s", exc)
            return _keyword_only(db, question, filters)

    def filter_authorized_units(self, db: Session, user_id: int, unit_codes: list[str]) -> tuple:
        """调用 POST /api/knowledge/check-permissions，过滤用户无权访问的投融资知识单元。

        返回 (authorized_codes, unauthorized_codes, unauthorized_units)，
        其中 unauthorized_units 为含 title 的对象列表，供前端权限缺失卡片展示。
        """
        rows = db.execute(
            select(
                KnowledgeUnit.id,
                KnowledgeUnit.unit_code,
                KnowledgeUnit.title,
                KnowledgeUnit.confidential_level,
            ).where(KnowledgeUnit.unit_code.in_(unit_codes))
        ).all()
        id_by_code = {code: (uid, title, cl) for uid, code, title, cl in rows}
        context = build_permission_context(db, user_id, [uid for uid, _, _ in id_by_code.values()])
        authorized: list[str] = []
        unauthorized: list[str] = []
        unauthorized_units: list[dict] = []
        for code in unit_codes:
            item = id_by_code.get(code)
            if item is None:
                unauthorized.append(code)
                unauthorized_units.append({"id": code, "unit_code": code, "title": code})
                continue
            uid, title, cl = item
            rules = db.execute(
                select(UnitPermission).where(UnitPermission.unit_id == uid)
            ).scalars()
            if _eval_rules(user_id, context, list(rules), confidential_level=cl):
                authorized.append(code)
            else:
                unauthorized.append(code)
                unauthorized_units.append({"id": uid, "unit_code": code, "title": title})
        return authorized, unauthorized, unauthorized_units

    def assemble_prompt(
        self,
        question: str,
        authorized_units: list[dict],
        history: list[dict],
    ) -> str:
        """仅对满足数据权限的投融资知识单元进行内容拼装。"""
        system = (
            "你是企业内部投融资知识库助手。仅依据以下【授权知识片段】回答，"
            "未授权内容不输出，禁止引用未给出的项目名称、行业、金额等元数据。"
            "引用时使用 [n] 标注，对应下方引用列表。"
        )
        history_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in history[-6:]
        )
        refs = []
        snippets = []
        for idx, unit in enumerate(authorized_units, start=1):
            snippets.append(
                f"[{idx}] {unit.get('title')}\n{unit.get('summary') or unit.get('content', '')[:1200]}"
            )
            refs.append(
                f"[{idx}] unit={unit.get('unit_code')} title={unit.get('title')}"
            )
        blocks = [
            f"# System\n{system}",
            f"# History\n{history_text or '(无)'}",
            f"# Authorized\n" + "\n\n".join(snippets) if snippets else "# Authorized\n(无授权片段)",
            f"# References\n" + "\n".join(refs) if refs else "# References\n(无)",
            f"# Question\n{question}",
        ]
        return "\n\n".join(blocks)

    async def chat_stream(
        self,
        db: Session,
        user_id: int,
        question: str,
        session_id: str | None,
    ) -> AsyncIterator[dict]:
        """POST /api/ai/chat/stream：SSE 流式问答。

        事件流：status(retrieving) → trace → status(thinking) → status(generating) → answer* → sources → done
        """
        start = time.time()

        def _status(stage: str, message: str) -> dict:
            return {
                "event": "status",
                "data": json.dumps({"stage": stage, "message": message}, ensure_ascii=False),
            }

        # 阶段1：检索知识
        yield _status("retrieving", "正在检索投融资知识库…")

        user_context = self.validate_login(db, user_id)
        sess = self.manage_session(db, user_id, session_id)
        sid = sess["session_id"]
        filters = build_retrieval_filters(user_context)
        candidates = self.retrieve_candidates(db, question, user_context, filters)
        recalled_ids = [c["id"] for c in candidates]
        auth_ids, unauth_ids, unauth_units = self.filter_authorized_units(db, user_id, recalled_ids)
        authorized_units = [c for c in candidates if c["id"] in set(auth_ids)]
        # 重排并截断到 TOP_K，提升相关性、减少 token 消耗
        authorized_units = rerank(authorized_units, question, user_context)
        db.add(QaMessage(session_id=sid, role="user", content=question))
        db.commit()

        trace_id = str(uuid.uuid4())
        permission_missing = self.emit_permission_missing_notice(unauth_ids) if unauth_ids else ""

        yield {
            "event": "trace",
            "data": json.dumps(
                {
                    "trace_id": trace_id,
                    "session_id": sid,
                    "user_id": user_id,
                    "question": question,
                    "retrieval_filters": filters,
                    "recalled_unit_ids": recalled_ids,
                    "authorized_unit_ids": auth_ids,
                    "unauthorized_unit_ids": unauth_ids,
                    "sensitive_question_flag": detect_sensitive_question(question),
                },
                ensure_ascii=False,
            ),
        }

        # 阶段2：命中授权片段后，进入组织回答阶段
        yield _status("thinking", f"已检索到 {len(authorized_units)} 个相关片段，正在组织回答…")

        history = _load_history(db, sid)
        prompt = self.assemble_prompt(question, authorized_units, history)
        guard_prompt_injection(prompt)

        # 阶段3：LLM 流式生成
        yield _status("generating", "正在生成回答…")

        full_answer = ""
        usage: dict = {}
        async for chunk in self.stream_answer(prompt, usage):
            full_answer += chunk
            yield {"event": "answer", "data": json.dumps({"chunk": chunk}, ensure_ascii=False)}
        if permission_missing:
            yield {
                "event": "permission_missing",
                "data": json.dumps({"message": permission_missing, "unit_ids": unauth_ids, "units": unauth_units}, ensure_ascii=False),
            }
        # 仅保留 LLM 实际通过 [n] 引用的单元（assemble_prompt 中编号 1..len(authorized_units)）。
        # 若 LLM 一个 [n] 都未标（懒标/拒答），回退到全部授权单元避免 sources 为空。
        cited_units = _filter_cited_units(full_answer, authorized_units)
        citations = build_citation_block(cited_units)
        yield {"event": "sources", "data": json.dumps(citations, ensure_ascii=False)}
        yield {
            "event": "done",
            "data": json.dumps(
                {
                    "trace_id": trace_id,
                    "answer": full_answer,
                    "citations": citations,
                    "confidence": compute_answer_confidence(authorized_units, []),
                    "permission_missing_notices": [permission_missing] if permission_missing else [],
                    "latency_ms": int((time.time() - start) * 1000),
                    "usage": usage,
                },
                ensure_ascii=False,
            ),
        }
        db.add(QaMessage(session_id=sid, role="assistant", content=full_answer))
        session = db.execute(
            select(QaSession).where(QaSession.session_id == sid)
        ).scalar_one()
        if not session.title:
            session.title = question[:80]
        db.commit()
        record_access_log_async(
            db,
            {
                "session_id": sid,
                "user_id": user_id,
                "question": question,
                "answer": full_answer,
                "recalled_unit_ids_json": recalled_ids,
                "authorized_unit_ids_json": auth_ids,
                "unauthorized_unit_ids_json": unauth_ids,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "response_time_ms": int((time.time() - start) * 1000),
            },
        )

    async def stream_answer(self, prompt: str, usage: dict | None = None) -> AsyncIterator[str]:
        """生成并返回流式 Markdown 回答（SSE 事件生产者）。

        usage（可选 dict）会被填充 prompt_tokens/completion_tokens/total_tokens，
        用于看板 Token 统计；网关不返回 usage 时保持为空（不阻塞流）。
        """
        if settings.llm_api_key == "sk-xxx":
            text = (
                "（占位回答）当前未配置 LLM API Key。\n\n"
                "以下是依据授权知识片段拟定的回答：\n\n"
                + _placeholder_answer(prompt)
            )
            for i in range(0, len(text), 32):
                yield text[i : i + 32]
            return
        produced = False
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_api_base)
            try:
                stream = await client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": prompt.split("# Question")[0]},
                        {"role": "user", "content": prompt.split("# Question")[-1]},
                    ],
                    temperature=_TEMPERATURE,
                    max_tokens=_MAX_TOKENS,
                    stream=True,
                    stream_options={"include_usage": True},  # 部分网关返回 usage（最后一块）
                )
            except TypeError:
                # 网关不支持 stream_options 时降级
                stream = await client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": prompt.split("# Question")[0]},
                        {"role": "user", "content": prompt.split("# Question")[-1]},
                    ],
                    temperature=_TEMPERATURE,
                    max_tokens=_MAX_TOKENS,
                    stream=True,
                )
            async for event in stream:
                # usage 通常出现在最后一个 chunk（choices 为空）
                usage_data = getattr(event, "usage", None)
                if usage_data and usage is not None:
                    usage["prompt_tokens"] = getattr(usage_data, "prompt_tokens", None)
                    usage["completion_tokens"] = getattr(usage_data, "completion_tokens", None)
                    usage["total_tokens"] = getattr(usage_data, "total_tokens", None)
                delta = event.choices[0].delta.content if event.choices else None
                if delta:
                    produced = True
                    yield delta
        except Exception as exc:
            logger.error("LLM 调用失败: %s", exc)
            yield f"\n\n[LLM 调用失败：{exc}]"
            return
        if not produced:
            yield "\n\n（模型未返回有效内容，请稍后重试或联系管理员。）"

    def emit_permission_missing_notice(self, unauthorized_unit_ids: list[int]) -> str:
        """在回复或引用来源中明确告知缺失对应项目知识单元的访问权限。"""
        if not unauthorized_unit_ids:
            return ""
        return "以下内容因缺少项目数据权限未纳入回答。"


# ----------- 问答追踪辅助方法（技能文档 03：细化方法） -----------
def build_retrieval_filters(context: dict) -> dict:
    """根据团队、基金/项目范围、行业、轮次、状态生成过滤条件。"""
    return {
        "user_id": context.get("user_id"),
        "department_ids": context.get("department_ids", []),
        "role_ids": context.get("role_ids", []),
    }


def hybrid_search(query: str, filters: dict, top_k: int = _RECALL_TOP_K) -> list:
    """向量检索（Milvus ANN）+ 关键字检索（ES BM25），返回合并后的候选集和分数。"""
    vector_candidates = _vector_search(query, top_k)
    ensure_knowledge_index()
    bm25 = get_es_client().search(
        index=KNOWLEDGE_INDEX,
        query={"multi_match": {"query": query, "fields": ["title^2", "content"]}},
        size=top_k,
    )
    return _merge_results(vector_candidates, bm25)


def rerank(candidates: list, query: str, context: dict) -> list:
    """按标题命中、行业匹配、项目阶段、来源权重重新排序。"""
    q_tokens = set(query.lower().split())
    for c in candidates:
        bonus = 0.0
        title_tokens = set((c.get("title") or "").lower().split())
        bonus += 0.2 * len(q_tokens & title_tokens)
        if c.get("industry") in context.get("industries", []):
            bonus += 0.1
        c["rerank_score"] = c.get("score", 0) + bonus
    candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    return candidates[:_FINAL_TOP_K]


def resolve_multi_turn_context(history: list) -> dict:
    """从历史对话中提取项目名、行业、轮次等实体。"""
    text = "\n".join(m.get("content", "") for m in history)
    return {
        "project_name": None,
        "industry": None,
        "financing_round": None,
        "raw_text": text,
    }


def detect_sensitive_question(question: str) -> bool:
    """识别投资建议、未公开信息、个人信息、内部定价等问题。"""
    return any(k in question for k in _SENSITIVE_KEYWORDS)


def guard_prompt_injection(prompt: str) -> None:
    """防止知识片段中的恶意指令影响回答。"""
    blacklist = ("忽略以上", "ignore previous", "system:", "you are")
    if any(b in prompt.lower() for b in blacklist):
        return


def build_citation_block(units: list[dict]) -> list[dict]:
    """输出来源知识单元、标题、章节、更新时间。"""
    return [
        {
            "id": u.get("id"),
            "unit_code": u.get("unit_code"),
            "title": u.get("title"),
            "updated_at": u.get("updated_at"),
        }
        for u in units
    ]


_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def _filter_cited_units(answer: str, authorized_units: list[dict]) -> list[dict]:
    """从 LLM 回答中提取 [n] 引用标记（1-based，对应 authorized_units 列表），仅返回被引用的单元。

    设计目的：assemble_prompt 已要求 LLM 用 [n] 标注来源（n 与 snippets 顺序一致），
    前端「引用来源」面板只展示 LLM 真正用到的片段，避免把全部授权单元（可能含无关命中）都列出来。
    若 LLM 没有任何 [n] 标注（拒答/懒标/被截断），回退到全部授权单元，保证 sources 始终非空。
    """
    if not answer or not authorized_units:
        return authorized_units
    n_max = len(authorized_units)
    cited: set[int] = set()
    for m in _CITATION_PATTERN.finditer(answer):
        n = int(m.group(1))
        if 1 <= n <= n_max:
            cited.add(n - 1)
    if not cited:
        return authorized_units
    return [authorized_units[i] for i in sorted(cited)]


def compute_answer_confidence(units: list[dict], scores: list[float]) -> float:
    """基于召回分数和引用覆盖度输出低置信度标记。"""
    if not units:
        return 0.0
    avg = sum(scores) / len(scores) if scores else 0.5
    coverage = min(1.0, len(units) / _FINAL_TOP_K)
    return round(0.5 * avg + 0.5 * coverage, 2)


def _embed_query(question: str) -> list[float]:
    from app.utils.embeddings import embed_text

    return embed_text(question)


def _vector_search(question: str, top_k: int = _RECALL_TOP_K) -> list:
    """Milvus 向量近邻检索，返回候选列表（含元数据）。"""
    vector = _embed_query(question)
    return search_units(vector, top_k)


def _merge_with_keyword(question: str, vector_candidates: list) -> list:
    ensure_knowledge_index()
    bm25 = get_es_client().search(
        index=KNOWLEDGE_INDEX,
        query={"multi_match": {"query": question, "fields": ["title^2", "content"]}},
        size=_RECALL_TOP_K,
    )
    return _merge_results(vector_candidates, bm25)


def _merge_results(vector_candidates: list, bm25_resp) -> list:
    """合并 Milvus 向量候选（list[dict]）与 ES BM25 命中（响应体），按加权分数降序。

    BM25 原始分数无界，与 cosine（0~1）直接加权会主导排序；
    先将 BM25 分数按本批最大分归一化到 0~1，再按 0.7/0.3 加权融合。
    """
    bm25_hits = (bm25_resp or {}).get("hits", {}).get("hits", [])
    raw_bm25 = [float(hit.get("_score") or 0) for hit in bm25_hits]
    bm25_max = max(raw_bm25, default=0.0) or 1.0
    bm25_norm = {hit["_id"]: float(hit.get("_score") or 0) / bm25_max for hit in bm25_hits}

    merged: dict = {}
    for cand in vector_candidates:
        merged[cand["id"]] = {
            "id": cand["id"],
            "unit_code": cand["id"],
            "score": _HYBRID_VECTOR_WEIGHT * (cand.get("score") or 0),
            "title": cand.get("title"),
            "content": cand.get("content"),
            "summary": cand.get("summary"),
            "industry": cand.get("industry"),
            "financing_round": cand.get("financing_round"),
            "deal_stage": cand.get("deal_stage"),
            "confidential_level": cand.get("confidential_level"),
            "status": cand.get("status"),
        }
    for hit in bm25_hits:
        key = hit["_id"]
        norm = bm25_norm.get(key, 0.0)
        if key in merged:
            merged[key]["score"] += _HYBRID_KEYWORD_WEIGHT * norm
        else:
            src = hit.get("_source") or {}
            merged[key] = {
                "id": key,
                "unit_code": key,
                "score": _HYBRID_KEYWORD_WEIGHT * norm,
                "title": src.get("title"),
                "content": src.get("content"),
                "summary": src.get("summary"),
                "industry": src.get("industry"),
                "financing_round": src.get("financing_round"),
                "deal_stage": src.get("deal_stage"),
                "confidential_level": src.get("confidential_level"),
                "status": src.get("status"),
            }
    items = list(merged.values())
    items.sort(key=lambda x: x.get("score", 0), reverse=True)
    return items[:_RECALL_TOP_K]


def _keyword_only(db: Session, question: str, filters: dict) -> list:
    terms = _question_terms(question)
    if not terms:
        return []
    conds = [
        KnowledgeUnit.title.contains(t) | KnowledgeUnit.content.contains(t)
        for t in terms
    ]
    rows = db.execute(
        select(KnowledgeUnit).where(or_(*conds)).limit(_RECALL_TOP_K)
    ).scalars()
    return [
        {
            "id": u.unit_code,
            "unit_code": u.unit_code,
            "title": u.title,
            "summary": u.summary,
            "content": u.content,
            "score": 0.5,
        }
        for u in rows
    ]


def _question_terms(question: str) -> list[str]:
    """从提问中提取检索词：剥离语气/疑问短语，按连接词切分，剔除虚词与标点。"""
    import re

    stop_phrases = (
        "请", "帮忙", "告诉我", "帮我查一下", "帮我查", "查一下", "介绍一下",
        "介绍下", "介绍", "了解一下", "了解下", "了解", "请问", "我想知道",
        "什么", "哪些", "如何", "怎么", "为什么", "多少", "是否", "有没有",
        "的情况", "相关信息", "相关内容", "信息", "内容", "情况", "一下",
    )
    stop_chars = set("的了呢吗啊吧和与以及关于有关呀哦啊是么着")
    q = question.strip()
    changed = True
    while changed:
        changed = False
        for p in stop_phrases:
            if q.startswith(p):
                q = q[len(p):]
                changed = True
            if q.endswith(p) and len(q) > len(p):
                q = q[: -len(p)]
                changed = True
    tokens = re.split(
        r"[\s，。？、！；：,.?!;:'\"()（）\n\r\t]+|[的]+", q
    )
    terms: list[str] = []
    for t in tokens:
        t = "".join(ch for ch in t if ch not in stop_chars).strip()
        if t and len(t) >= 2 and t not in terms:
            terms.append(t)
    if not terms:
        terms = [question.strip()]
    return terms[:8]


def _eval_rules(user_id: int, context: dict, rules: list[UnitPermission], confidential_level: int = None) -> bool:
    if not rules:
        # 无显式权限配置时：公开级（confidential_level<=1）默认可读，其余默认拒绝
        if confidential_level is not None and confidential_level <= 1:
            return True
        return False
    has_allow = False
    has_deny = False
    for rule in rules:
        if rule.target_type == "deny":
            has_deny = True
        elif rule.target_type == "global":
            has_allow = True
        elif rule.target_type == "department" and rule.target_id in context.get("department_ids", []):
            has_allow = True
        elif rule.target_type == "role" and rule.target_id in context.get("role_ids", []):
            has_allow = True
        elif rule.target_type == "user" and rule.target_id == user_id:
            has_allow = True
    return has_allow and not has_deny


def _load_history(db: Session, session_id: str) -> list[dict]:
    rows = db.execute(
        select(QaMessage).where(QaMessage.session_id == session_id).order_by(QaMessage.created_at)
    ).scalars()
    return [{"role": m.role, "content": m.content or ""} for m in rows]


def _placeholder_answer(prompt: str) -> str:
    return (
        "1. 项目所处阶段与轮次需结合授权片段核实。\n"
        "2. 当前命中知识单元已通过数据权限校验。\n"
        "3. 具体结论以引用卡片为准。"
    )


ai_qa_service = AiQaService()