import json
import logging

import httpx

from app.config import Settings
from app.schemas import AssistantReply

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are CIVI, a Vietnamese public-service assistant in an early MVP.
Offer only general, cautious guidance. Do not state legal requirements as facts, invent
citations, decide administrative eligibility, or claim that procedures are verified.
Explain that official information and RAG data are not available yet when relevant.
Reply in the user's requested language. Return JSON only with intent, answer, quick_replies.
intent is one of procedure_guidance, form_guidance, general, out_of_scope."""


def mock_reply(language_code: str) -> AssistantReply:
    is_vietnamese = language_code.lower().startswith("vi")
    answer = (
        "Tôi đã ghi nhận yêu cầu của bạn. Phiên bản thử nghiệm này chưa có dữ liệu thủ tục "
        "chính thức để tra cứu, nên tôi chỉ có thể hướng dẫn ở mức chung. Bạn có thể cho biết "
        "bạn muốn thực hiện việc gì hoặc đang ở tỉnh/thành phố nào?"
        if is_vietnamese
        else "I have recorded your request. This early version does not yet have official procedure data, so I can only provide general guidance."
    )
    return AssistantReply(intent="general", answer=answer, quick_replies=[])


class OpenAICompatibleClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def reply(self, messages: list[dict[str, str]], language_code: str) -> AssistantReply:
        if not self.settings.llm_api_key or not self.settings.llm_model:
            return mock_reply(language_code)

        payload = {
            "model": self.settings.llm_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": f"{SYSTEM_PROMPT}\nRequested language code: {language_code}."},
                *messages,
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return AssistantReply.model_validate(json.loads(content))
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning("llm_fallback reason=%s", type(exc).__name__)
            return mock_reply(language_code)
