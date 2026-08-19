"""文本向量化（供知识单元同步与问答召回使用）。

provider=api（默认，推荐云服务器）：调用 OpenAI 兼容 Embedding 网关
（如 SiliconFlow https://api.siliconflow.cn/v1），无本地权重；
provider=local：本地 bge-m3 模型（sentence-transformers 加载），进程内单例复用。
"""
import logging
import os
from threading import Lock

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = Lock()
_client: OpenAI | None = None
_client_lock = Lock()

# 向量维度，需与 Milvus 集合向量字段（app/core/milvus.py）保持一致
EMBEDDING_DIM = settings.embedding_dim

# API 模式单次请求最大条数（SiliconFlow 批量上限友好值）
_API_BATCH_SIZE = 16


def _get_client() -> OpenAI:
    """惰性创建 OpenAI 兼容 Embedding 客户端（进程内单例）。"""
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        if not settings.embedding_api_key or settings.embedding_api_key.startswith("sk-REPLACE"):
            raise RuntimeError(
                "EMBEDDING_API_KEY 未配置：API 向量化需要 OpenAI 兼容网关的密钥，"
                "请在 .env 中配置 EMBEDDING_API_KEY。"
            )
        _client = OpenAI(
            base_url=settings.embedding_api_base,
            api_key=settings.embedding_api_key,
            timeout=120,
            max_retries=2,
        )
        logger.info(
            "embedding 客户端就绪: base=%s model=%s dim=%d",
            settings.embedding_api_base,
            settings.embedding_model,
            EMBEDDING_DIM,
        )
        return _client


def _embed_api(texts: list[str]) -> list[list[float]]:
    """调用 OpenAI 兼容网关批量向量化，返回按输入顺序排列的向量列表。"""
    client = _get_client()
    resp = client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
        encoding_format="float",
    )
    items = sorted(resp.data, key=lambda d: d.index)
    vectors = [item.embedding for item in items]
    for v in vectors:
        if len(v) != EMBEDDING_DIM:
            raise RuntimeError(
                f"embedding 网关返回维度 {len(v)}，与 EMBEDDING_DIM={EMBEDDING_DIM} 不一致，"
                f"请检查 EMBEDDING_MODEL 是否与 Milvus 集合维度匹配。"
            )
    return vectors


def _get_model():
    """惰性加载本地 bge-m3 模型，进程内单例复用（provider=local 时使用）。"""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from sentence_transformers import SentenceTransformer

        model_path = settings.embedding_model_path
        if not os.path.isabs(model_path):
            # 以项目根目录为基准解析相对路径
            root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            model_path = os.path.join(root, model_path)
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"本地 embedding 模型不存在: {model_path}，"
                f"请检查 .env 中 EMBEDDING_MODEL_PATH 配置。"
            )
        logger.info("加载本地 embedding 模型: %s", model_path)
        _model = SentenceTransformer(
            model_path,
            device="cpu",  # 如需 GPU 改为 "cuda"
        )
        logger.info("embedding 模型加载完成，维度=%d", EMBEDDING_DIM)
        return _model


def embed_text(text: str) -> list[float]:
    """对文本进行向量化。"""
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """批量向量化。"""
    if not texts:
        return []
    if settings.embedding_provider == "api":
        vectors: list[list[float]] = []
        for i in range(0, len(texts), _API_BATCH_SIZE):
            vectors.extend(_embed_api(texts[i : i + _API_BATCH_SIZE]))
        return vectors
    model = _get_model()
    vectors = model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return [v.tolist() for v in vectors]
