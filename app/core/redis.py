"""Redis 连接（FAQ 缓存 / 会话缓存）。"""
import redis

from app.config import settings

redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """获取全局 Redis 客户端，未初始化时建立连接。"""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return redis_client
