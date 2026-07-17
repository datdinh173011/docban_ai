import pytest

from app.config import Settings


def test_database_url_is_required_when_database_is_used() -> None:
    settings = Settings(_env_file=None, database_url="")

    with pytest.raises(RuntimeError, match="DATABASE_URL must be configured"):
        settings.require_database_url()


def test_database_url_comes_from_runtime_settings() -> None:
    database_url = "postgresql+asyncpg://user:password@postgres:5432/database"

    settings = Settings(_env_file=None, database_url=database_url)

    assert settings.require_database_url() == database_url
