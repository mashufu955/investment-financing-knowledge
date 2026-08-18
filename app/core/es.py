"""Elasticsearch 连接与关键字(BM25)索引操作。

职责划分：向量存储与 ANN 检索由 Milvus 承担（见 app/core/milvus.py），
ES 仅保留标题/内容等文本字段用于关键字 BM25 检索（hybrid 召回的关键字路）。

覆盖技能 01 的 sync_vector_index 流程中「关键字索引」部分：
建立知识关键字索引、按单元写入元数据、按 ID 删除。
"""
from elasticsearch import Elasticsearch

from app.config import settings

es_client: Elasticsearch | None = None

KNOWLEDGE_INDEX = f"{settings.es_index_prefix}_units"


def get_es_client() -> Elasticsearch:
    """获取全局 ES 客户端，未初始化时建立连接。"""
    global es_client
    if es_client is None:
        es_client = Elasticsearch(settings.es_hosts)
    return es_client


def ensure_knowledge_index() -> None:
    """确保知识关键字索引存在（仅文本/标量字段，不含向量）。"""
    client = get_es_client()
    if client.indices.exists(index=KNOWLEDGE_INDEX):
        return
    client.indices.create(
        index=KNOWLEDGE_INDEX,
        mappings={
            "properties": {
                "unit_id": {"type": "keyword"},
                "title": {"type": "text"},
                "content": {"type": "text"},
                "summary": {"type": "text"},
                "industry": {"type": "keyword"},
                "financing_round": {"type": "keyword"},
                "deal_stage": {"type": "keyword"},
                "confidential_level": {"type": "integer"},
                "status": {"type": "keyword"},
            }
        },
    )


def index_keyword_unit(unit_id: str, metadata: dict) -> None:
    """写入单个知识单元的关键字索引（不含向量，向量见 Milvus）。"""
    client = get_es_client()
    client.index(
        index=KNOWLEDGE_INDEX,
        id=str(unit_id),
        document={"unit_id": unit_id, **metadata},
        refresh="wait_for",
    )


def delete_unit_from_index(unit_id: str) -> None:
    """按单元 ID 从关键字索引删除。"""
    client = get_es_client()
    client.delete(index=KNOWLEDGE_INDEX, id=str(unit_id), ignore=[404], refresh="wait_for")
