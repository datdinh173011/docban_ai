from pathlib import Path

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from app import form_export
from app.config import Settings
from app.main import create_app

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test"

_DEV_FALLBACK_FONTS = (
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
)


def _available_font() -> Path | None:
    return next((path for path in _DEV_FALLBACK_FONTS if path.is_file()), None)


@pytest.fixture
def app():
    return create_app(
        Settings(llm_api_key="", llm_model="", environment="LOCAL", session_ttl_seconds=1800, database_url=TEST_DATABASE_URL),
        FakeRedis(decode_responses=True),
    )


VALID_BIRTH_VALUES = {
    "applicant_full_name": "Nguyễn Văn An",
    "relationship_to_child": "Cha",
    "child_full_name": "Nguyễn Thị Hồng Ánh",
    "child_birth_date": "2026-01-01",
    "child_gender": "Nữ",
    "child_ethnicity": "Kinh",
    "child_nationality": "Việt Nam",
    "child_birth_place": "Bệnh viện Phụ sản Hà Nội",
    "mother_full_name": "Trần Thị Bích",
    "copy_request_needed": "Không",
}


@pytest.mark.asyncio
async def test_cors_preflight_allows_put_for_draft_endpoint(app) -> None:
    """Regression test: browsers send a PUT preflight for the draft endpoint's
    Content-Type: application/json body; if "PUT" is missing from the CORS
    middleware's allow_methods, the browser silently blocks the real request
    with no server-side trace (httpx/TestClient calls don't enforce this, so
    only a real browser or an explicit OPTIONS check catches it)."""
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.options(
                "/api/v1/forms/BIRTH_REGISTRATION_FORM/draft",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "PUT",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]


@pytest.mark.asyncio
async def test_production_startup_requires_a_vietnamese_pdf_font(monkeypatch) -> None:
    def missing_font() -> None:
        raise form_export.ExportError(None, "vietnamese_font_missing")

    monkeypatch.setattr("app.main.ensure_vietnamese_font", missing_font)
    production_app = create_app(
        Settings(llm_api_key="", llm_model="", environment="PRODUCTION", database_url=TEST_DATABASE_URL),
        FakeRedis(decode_responses=True),
    )
    with pytest.raises(form_export.ExportError, match="vietnamese_font_missing"):
        async with production_app.router.lifespan_context(production_app):
            pass


@pytest.mark.asyncio
async def test_form_schema_returns_groups_and_fields(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/forms/BIRTH_REGISTRATION_FORM/schema")
    assert response.status_code == 200
    body = response.json()
    assert body["form_code"] == "BIRTH_REGISTRATION_FORM"
    assert any(field["field_code"] == "child_full_name" for field in body["fields"])


@pytest.mark.asyncio
async def test_unknown_form_code_is_404(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/forms/NOT_A_FORM/schema")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_draft_update_and_get_round_trip(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            put_response = await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": {"child_full_name": "Nguyễn Thị Hồng Ánh"}})
            assert put_response.status_code == 200
            assert put_response.json()["fields"]["child_full_name"] == "Nguyễn Thị Hồng Ánh"

            get_response = await client.get("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft")
            assert get_response.status_code == 200
            assert get_response.json()["fields"]["child_full_name"] == "Nguyễn Thị Hồng Ánh"


@pytest.mark.asyncio
async def test_validate_reports_missing_required_fields(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": {"child_full_name": "Nguyễn Thị Hồng Ánh"}})
            response = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"
    assert body["summary"]["blocking_error"] > 0


@pytest.mark.asyncio
async def test_export_rejects_stale_validation_id(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": VALID_BIRTH_VALUES})
            response = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/exports/pdf", json={"validation_id": "not-a-real-id"})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_export_rejects_when_draft_changed_after_validation(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": VALID_BIRTH_VALUES})
            validation = (await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")).json()
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": {"child_full_name": "Đã sửa"}})
            response = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/exports/pdf", json={"validation_id": validation["validation_id"]})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_export_rejects_blocking_errors(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": {"child_full_name": "Chỉ một trường"}})
            validation = (await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")).json()
            assert validation["status"] == "invalid"
            response = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/exports/pdf", json={"validation_id": validation["validation_id"]})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_full_happy_path_produces_a_pdf(app, monkeypatch) -> None:
    font_path = _available_font()
    if font_path is None:
        pytest.skip("no Unicode-complete TTF available on this machine to exercise the real render path")
    monkeypatch.setattr(form_export, "_FONT_CANDIDATES", (font_path,))
    monkeypatch.setattr(form_export, "_registered", False)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": VALID_BIRTH_VALUES})
            validation = (await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")).json()
            assert validation["status"] == "valid"
            response = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/exports/pdf", json={"validation_id": validation["validation_id"]})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"
