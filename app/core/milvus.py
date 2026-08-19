"""Milvus 连接与向量索引操作。

覆盖技能 01 的 sync_vector_index 流程与技能 03 的向量召回：
建立知识向量集合、按单元写入向量与元数据、按 ID 删除、向量近邻检索。

职责划分：Milvus 承担向量存储与 ANN 检索；Elasticsearch 仅保留
关键字(BM25)检索（见 app/core/es.py），避免向量冗余存储。
"""
import logging

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.config import settings
from app.utils.embeddings import EMBEDDING_DIM

logger = logging.getLogger(__name__)

COLLECTION_NAME = f"{settings.milvus_collection_prefix}_units"
_MILVUS_ALIAS = "default"

def _index_params() -> dict:
    """向量索引参数：Milvus Lite 仅支持 FLAT/IVF_FLAT/AUTOINDEX，独立 Milvus 用 HNSW。"""
    if settings.milvus_lite_uri:
        return {"index_type": "FLAT", "metric_type": "COSINE", "params": {}}
    return {
        "index_type": "HNSW",
        "metric_type": "COSINE",
        "params": {"M": 16, "efConstruction": 200},
    }


def _search_params() -> dict:
    """检索参数：Lite 用 FLAT 无需 ef，独立 Milvus 用 HNSW ef。"""
    if settings.milvus_lite_uri:
        return {"metric_type": "COSINE", "params": {}}
    return {"metric_type": "COSINE", "params": {"ef": 64}}

_connected = False
_collection: Collection | None = None


def _connect() -> None:
    """惰性建立 Milvus 连接（进程内单例）。"""
    global _connected
    if _connected:
        return
    if settings.milvus_lite_uri:
        connections.connect(
            alias=_MILVUS_ALIAS,
            uri=settings.milvus_lite_uri,
            timeout=30,
        )
    else:
        connections.connect(
            alias=_MILVUS_ALIAS,
            host=settings.milvus_host,
            port=str(settings.milvus_port),
            timeout=30,
        )
    _connected = True


def _schema() -> CollectionSchema:
    """知识单元向量集合的 schema：主键 + 向量 + 标量元数据。"""
    fields = [
        FieldSchema(name="unit_id", dtype=DataType.VARCHAR, max_length=64, is_primary=True, auto_id=False),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=1024),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="summary", dtype=DataType.VARCHAR, max_length=1024),
        FieldSchema(name="industry", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="financing_round", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="deal_stage", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="confidential_level", dtype=DataType.INT32),
        FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=32),
    ]
    return CollectionSchema(fields, description="投融资知识单元向量")


def _ensure_index(collection: Collection) -> None:
    """确保 embedding 字段存在向量索引。"""
    if any(idx.field_name == "embedding" for idx in collection.indexes):
        return
    collection.create_index(field_name="embedding", index_params=_index_params())


def ensure_knowledge_collection() -> Collection:
    """确保知识向量集合存在（建集合 + 建向量索引 + 加载），返回集合句柄。"""
    global _collection
    _connect()
    if _collection is not None:
        return _collection
    if utility.has_collection(COLLECTION_NAME, using=_MILVUS_ALIAS):
        collection = Collection(COLLECTION_NAME, using=_MILVUS_ALIAS)
    else:
        collection = Collection(COLLECTION_NAME, schema=_schema(), using=_MILVUS_ALIAS)
        logger.info("创建 Milvus 向量集合: %s", COLLECTION_NAME)
    _ensure_index(collection)
    collection.load()
    _collection = collection
    return collection


def _row(unit_id: str, vector: list[float], metadata: dict) -> dict:
    """将元数据清洗为 Milvus 实体行（标量字段不允许 None）。unit_id 使用业务编号 unit_code。"""
    return {
        "unit_id": str(unit_id),
        "embedding": [float(x) for x in vector],
        "title": str(metadata.get("title") or ""),
        "content": str(metadata.get("content") or ""),
        "summary": str(metadata.get("summary") or ""),
        "industry": str(metadata.get("industry") or ""),
        "financing_round": str(metadata.get("financing_round") or ""),
        "deal_stage": str(metadata.get("deal_stage") or ""),
        "confidential_level": int(metadata.get("confidential_level") or 0),
        "status": str(metadata.get("status") or ""),
    }


def index_unit(unit_id: str, vector: list[float], metadata: dict) -> None:
    """写入单个知识单元的向量与元数据（upsert，同主键覆盖）。unit_id 使用业务编号 unit_code。"""
    collection = ensure_knowledge_collection()
    collection.upsert([_row(unit_id, vector, metadata)])


def delete_unit_from_index(unit_id: str) -> None:
    """按单元编号（unit_code）从向量集合删除。"""
    collection = ensure_knowledge_collection()
    collection.delete(f'unit_id in ["{unit_id}"]')
    _flush(collection)


def flush_knowledge_collection() -> None:
    """将挂起的 upsert 落盘，保证写入立即可检索。"""
    try:
        _flush(ensure_knowledge_collection())
    except Exception:  # noqa: BLE001
        logger.exception("Milvus flush 失败（数据最终一致，稍后可见）")


def _flush(collection: Collection) -> None:
    collection.flush()


def search_units(vector: list[float], top_k: int, filters: dict | None = None) -> list:
    """向量近邻检索，返回按相似度降序的候选列表（含元数据）。

    filters 保留给后续标量过滤扩展，当前与 ES KNN 阶段行为保持一致：
    权限过滤放在召回之后（见 ai_qa_service.filter_authorized_units）。
    """
    collection = ensure_knowledge_collection()
    results = collection.search(
        data=[list(vector)],
        anns_field="embedding",
        param=_search_params(),
        limit=top_k,
        output_fields=[
            "title",
            "content",
            "summary",
            "industry",
            "financing_round",
            "deal_stage",
            "confidential_level",
            "status",
        ],
    )
    hits = results[0] if results else []
    return [
        {
            "id": hit.id,
            "score": float(hit.score),
            "title": hit.entity.get("title"),
            "content": hit.entity.get("content"),
            "summary": hit.entity.get("summary"),
            "industry": hit.entity.get("industry"),
            "financing_round": hit.entity.get("financing_round"),
            "deal_stage": hit.entity.get("deal_stage"),
            "confidential_level": hit.entity.get("confidential_level"),
            "status": hit.entity.get("status"),
        }
        for hit in hits
    ]
