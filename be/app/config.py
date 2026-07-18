from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
    )

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    environment: Literal["LOCAL", "PRODUCTION"] = "PRODUCTION"
    llm_debug_logging: bool = False
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    procedure_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    procedure_embedding_dimensions: int = 384
    procedure_embedding_device: str = "cpu"
    procedure_chunk_max_chars: int = 1200
    procedure_chunk_overlap_chars: int = 200
    external_search_enabled: bool = False
    external_search_timeout_seconds: int = 10
    external_search_result_limit: int = 5
    external_search_allowed_domains: str = ""
    database_url: str = ""
    knowledge_data_dir: Path = Path(__file__).resolve().parents[1] / "runtime_data"
    procedure_snapshot_dir: Path = Path(__file__).resolve().parents[1] / "data" / "dichvucong_xaydung"
    procedure_catalog_path: Path | None = None
    procedure_review_registry_path: Path | None = None
    retrieval_limit: int = 6
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 1800
    max_message_length: int = 2000
    cors_origin: str = "http://localhost:5173"
    session_cookie_name: str = "icivi_session"
    session_cookie_secure: bool = False

    def require_database_url(self) -> str:
        if not self.database_url:
            raise RuntimeError("DATABASE_URL must be configured in the runtime environment")
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
