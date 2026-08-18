"""应用配置：从环境变量 / .env 读取。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 应用
    app_name: str = "investment-finance"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 120

    # MySQL
    mysql_host: str = "106.55.0.45"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "change-me"
    mysql_database: str = "investment_finance"

    # Elasticsearch（仅作关键字 BM25 检索）
    es_hosts: str = "http://106.55.0.45:9200"
    es_index_prefix: str = "if_knowledge"

    # Milvus（向量存储与 ANN 检索）
    milvus_host: str = "106.55.0.45"
    milvus_port: int = 19530
    milvus_collection_prefix: str = "if_knowledge"

    # Redis
    redis_url: str = "redis://106.55.0.45:6379/0"

    # 大模型
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = "sk-xxx"
    llm_model: str = "gpt-4o"
    embedding_model: str = "bge-m3"
    embedding_model_path: str = "models/BAAI/bge-m3"

    # 本地模型根目录
    models_dir: str = "models"

    # 上传
    upload_dir: str = "./uploads"
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
