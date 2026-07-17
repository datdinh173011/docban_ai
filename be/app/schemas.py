from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    language_code: str = Field(default="vi", min_length=2, max_length=12)


class AssistantReply(BaseModel):
    intent: Literal["procedure_guidance", "form_guidance", "general", "out_of_scope"]
    answer: str = Field(min_length=1, max_length=4000)
    quick_replies: list[str] = Field(default_factory=list, max_length=3)
