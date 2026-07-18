import pytest

from app.config import Settings
from app.form_conversation import maybe_fill_form, resolve_form_code
from app.procedure_settings import load_procedure_settings
from app.schemas import AssistantReply

SETTINGS = load_procedure_settings()


def test_resolve_form_code_by_keyword() -> None:
    assert resolve_form_code(None, "Tôi muốn đăng ký khai sinh cho con", SETTINGS.form_mappings) == "BIRTH_REGISTRATION_FORM"
    assert resolve_form_code(None, "làm sao đăng ký thường trú", SETTINGS.form_mappings) == "PERMANENT_RESIDENCE_CT01_FORM"
    assert resolve_form_code(None, "xin giấy phép xây dựng nhà ở riêng lẻ", SETTINGS.form_mappings) == "CONSTRUCTION_PERMIT_REQUEST_FORM"


def test_resolve_form_code_by_procedure_code_takes_priority() -> None:
    assert resolve_form_code("1.013225", "không liên quan gì cả", SETTINGS.form_mappings) == "CONSTRUCTION_PERMIT_REQUEST_FORM"


def test_resolve_form_code_returns_none_for_unrelated_message() -> None:
    assert resolve_form_code(None, "thủ tục cấp phép khai thác cát", SETTINGS.form_mappings) is None


@pytest.mark.asyncio
async def test_maybe_fill_form_is_noop_for_unrelated_procedure() -> None:
    state = {"active_scenario_code": None, "form_draft": {}, "language_code": "vi"}
    result = {"reply": AssistantReply(intent="procedure_guidance", answer="ok", quick_replies=[]), "active_procedure_code": None}
    messages = [{"role": "user", "content": "hỏi về thủ tục khác không liên quan"}]
    reply, patch = await maybe_fill_form(state, result, Settings(), SETTINGS, messages)
    assert reply is result["reply"]
    assert patch is None


@pytest.mark.asyncio
async def test_maybe_fill_form_uses_mock_reply_without_llm_key() -> None:
    state = {"active_scenario_code": None, "form_draft": {}, "language_code": "vi"}
    result = {"reply": AssistantReply(intent="general", answer="ok", quick_replies=[]), "active_procedure_code": None}
    messages = [{"role": "user", "content": "tôi muốn đăng ký khai sinh cho bé"}]
    reply, patch = await maybe_fill_form(state, result, Settings(llm_api_key="", llm_model=""), SETTINGS, messages)
    assert reply.intent == "form_guidance"
    assert patch is not None
    assert patch["form_code"] == "BIRTH_REGISTRATION_FORM"
