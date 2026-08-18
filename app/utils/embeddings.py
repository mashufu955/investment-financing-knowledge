"""文本向量化（供知识单元同步与问答召回使用）。

使用本地 bge-m3 模型（sentence-transformers 加载），首次调用时惰性加载，
进程内复用单例，避免重复占用显存/内存。
"""
import logging
import os
from threading import Lock

from app.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = Lock()

# bge-m3 向量维度，需与 Milvus 集合向量字段（app/core/milvus.py）保持一致
EMBEDDING_DIM = 1024


def _get_model():
    """惰性加载本地 bge-m3 模型，进程内单例复用。"""
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
    model = _get_model()
    vectors = model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return [v.tolist() for v in vectors]
