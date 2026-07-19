import json
import logging

import httpx
import pytest

from app.config import Settings
from app.form_ai_review import ai_review_form, merge_ai_issues
from app.form_validation import validate_form
from app.procedure_settings import load_procedure_settings
from app.schemas import ValidationIssue

SETTINGS = load_procedure_settings()
BIRTH_FORM = SETTINGS.form_candidates["BIRTH_REGISTRATION_FORM"]

VALID_BIRTH_VALUES = {
    "applicant_full_name": "Nguyễn Văn An",
    "applicant_birth_date": "1990-01-01",
    "applicant_residence": "Hà Nội",
    "applicant_id_document": "012345678901",
    "relationship_to_child": "Cha",
    "child_full_name": "Nguyễn Thị Hồng Ánh",
    "child_birth_date": "2026-01-01",
    "child_gender": "Nữ",
    "child_ethnicity": "Kinh",
    "child_nationality": "Việt Nam",
    "child_birth_place": "Bệnh viện Phụ sản Hà Nội",
    "child_hometown": "Hà Nội",
    "mother_full_name": "Trần Thị Bích",
    "mother_birth_year": "1992",
    "mother_ethnicity": "Kinh",
    "mother_nationality": "Việt Nam",
    "mother_residence": "Hà Nội",
    "mother_id_document": "012345678902",
    "copy_request_needed": "Không",
    "copy_count": 0,
}


class FakeResponse:
    status_code = 200
    headers = {"content-type": "application/json"}

    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


class FakeAsyncClient:
    payload: dict | None = None
    reply_content: str = "{}"

    def __init__(self, *args, **kwargs) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def post(self, url: str, json: dict, headers: dict) -> FakeResponse:
        FakeAsyncClient.payload = json
        return FakeResponse(FakeAsyncClient.reply_content)


@pytest.mark.asyncio
async def test_missing_llm_config_skips_ai_review_without_a_network_call() -> None:
    settings = Settings(llm_api_key="", llm_model="")
    issues = await ai_review_form(settings, BIRTH_FORM, VALID_BIRTH_VALUES, [])
    assert issues == []


@pytest.mark.asyncio
async def test_ai_issue_on_a_clean_field_is_returned_and_tagged(monkeypatch) -> None:
    FakeAsyncClient.reply_content = json.dumps({
        "issues": [{
            "field_code": "child_full_name",
            "issue_code": "IMPLAUSIBLE_NAME",
            "severity": "warning",
            "message_vi": "Tên có vẻ không hợp lý.",
            "suggestion_vi": None,
        }],
    })
    monkeypatch.setattr("app.form_ai_review.httpx.AsyncClient", FakeAsyncClient)
    settings = Settings(llm_api_key="test-key", llm_model="test-model")

    issues = await ai_review_form(settings, BIRTH_FORM, VALID_BIRTH_VALUES, [])

    assert len(issues) == 1
    assert issues[0].field_code == "child_full_name"
    assert issues[0].rule_code == "AI_IMPLAUSIBLE_NAME"
    assert issues[0].severity == "warning"


@pytest.mark.asyncio
async def test_ai_issue_referencing_unknown_field_is_dropped(monkeypatch, caplog) -> None:
    caplog.set_level(logging.WARNING, logger="app.form_ai_review")
    FakeAsyncClient.reply_content = json.dumps({
        "issues": [{
            "field_code": "not_a_real_field",
            "issue_code": "HALLUCINATED",
            "severity": "warning",
            "message_vi": "Nội dung không có căn cứ.",
        }],
    })
    monkeypatch.setattr("app.form_ai_review.httpx.AsyncClient", FakeAsyncClient)
    settings = Settings(llm_api_key="test-key", llm_model="test-model")

    issues = await ai_review_form(settings, BIRTH_FORM, VALID_BIRTH_VALUES, [])

    assert issues == []
    assert any("form_ai_review_unknown_field" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_malformed_provider_response_degrades_to_empty(monkeypatch, caplog) -> None:
    caplog.set_level(logging.WARNING, logger="app.form_ai_review")
    FakeAsyncClient.reply_content = "not valid json"
    monkeypatch.setattr("app.form_ai_review.httpx.AsyncClient", FakeAsyncClient)
    settings = Settings(llm_api_key="test-key", llm_model="test-model")

    issues = await ai_review_form(settings, BIRTH_FORM, VALID_BIRTH_VALUES, [])

    assert issues == []
    assert any("form_ai_review_fallback" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_provider_http_error_degrades_to_empty(monkeypatch) -> None:
    class ErrorResponse:
        status_code = 500

        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError("boom", request=httpx.Request("POST", "https://example.test"), response=self)

    class FailingAsyncClient(FakeAsyncClient):
        async def post(self, url: str, json: dict, headers: dict) -> FakeResponse:
            return ErrorResponse()

    monkeypatch.setattr("app.form_ai_review.httpx.AsyncClient", FailingAsyncClient)
    settings = Settings(llm_api_key="test-key", llm_model="test-model")

    issues = await ai_review_form(settings, BIRTH_FORM, VALID_BIRTH_VALUES, [])

    assert issues == []


def test_merge_adds_ai_issue_and_escalates_status_to_invalid() -> None:
    base_result = validate_form(BIRTH_FORM, VALID_BIRTH_VALUES)
    assert base_result.status == "valid"
    ai_issue = ValidationIssue(
        issue_code="IMPLAUSIBLE_ADDRESS",
        rule_code="AI_IMPLAUSIBLE_ADDRESS",
        field_code="child_birth_place",
        severity="blocking_error",
        message_vi="Nơi sinh không giống một cơ sở y tế.",
        suggestion_vi=None,
    )

    merged = merge_ai_issues(base_result, [ai_issue])

    assert merged.status == "invalid"
    assert merged.summary.blocking_error == 1
    assert any(issue.rule_code == "AI_IMPLAUSIBLE_ADDRESS" for issue in merged.issues)


def test_merge_activates_unable_to_validate_status() -> None:
    base_result = validate_form(BIRTH_FORM, VALID_BIRTH_VALUES)
    assert base_result.status == "valid"
    ai_issue = ValidationIssue(
        issue_code="UNCERTAIN_NAME",
        rule_code="AI_UNCERTAIN_NAME",
        field_code="child_full_name",
        severity="unable_to_verify",
        message_vi="Không đủ căn cứ để kết luận.",
        suggestion_vi=None,
    )

    merged = merge_ai_issues(base_result, [ai_issue])

    assert merged.status == "unable_to_validate"
    assert merged.summary.unable_to_verify == 1


def test_merge_never_drops_an_existing_rule_issue() -> None:
    base_result = validate_form(BIRTH_FORM, {})
    assert base_result.status == "invalid"
    rule_issue_count = len(base_result.issues)
    ai_issue_on_flagged_field = ValidationIssue(
        issue_code="ALSO_SUSPICIOUS",
        rule_code="AI_ALSO_SUSPICIOUS",
        field_code=base_result.issues[0].field_code,
        severity="suggestion",
        message_vi="Gợi ý thêm.",
        suggestion_vi=None,
    )

    merged = merge_ai_issues(base_result, [ai_issue_on_flagged_field])

    assert len(merged.issues) == rule_issue_count
    assert merged.status == "invalid"


def test_merge_is_a_noop_with_no_ai_issues() -> None:
    base_result = validate_form(BIRTH_FORM, VALID_BIRTH_VALUES)
    merged = merge_ai_issues(base_result, [])
    assert merged == base_result
