"""应用配置：从环境变量 / .env 读取。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 应用
    app_name: str = "investment-finance"
    app_env: str = "production"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 120

    # MySQL
    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "rootpass"
    mysql_database: str = "investment_finance"

    # Elasticsearch（仅作关键字 BM25 检索）
    es_hosts: str = "http://elasticsearch:9200"
    es_index_prefix: str = "if_knowledge"

    # Milvus（向量存储与 ANN 检索）
    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530
    # 嵌入式 Milvus Lite 文件路径（如 /app/data/milvus.db），非空时优先于 host/port；
    # 注意：变量名避开 pymilvus 保留的 MILVUS_URI（其导入时会按 http(s) 格式解析）
    milvus_lite_uri: str = "/app/data/milvus.db"
    milvus_collection_prefix: str = "if_knowledge"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # 大模型
    llm_api_base: str = "https://api.siliconflow.cn/v1"
    llm_api_key: str = ""  # 密钥必须由 .env 提供，禁止写死
    llm_model: str = "deepseek-ai/DeepSeek-V4-Flash"
    # 向量化：local=本地模型 / api=OpenAI 兼容网关（SiliconFlow 等）
    # 默认 api（OpenAI 兼容网关）；local 需本地模型权重，仅显式配置时启用
    embedding_provider: str = "api"
    embedding_api_base: str = "https://api.siliconflow.cn/v1"
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"
    embedding_model_path: str = "models/BAAI/bge-m3"
    embedding_dim: int = 1024

    # 本地模型根目录
    models_dir: str = "models"

    # CORS 允许来源（逗号分隔；生产通过 nginx 同源代理时可保持默认）
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 上传
    upload_dir: str = "/app/uploads"
    max_upload_mb: int = 50

    @property
    def mysql_dsn(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
