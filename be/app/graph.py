from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.llm import OpenAICompatibleClient
from app.schemas import AssistantReply


class ConversationState(TypedDict):
    messages: list[dict[str, str]]
    language_code: str
    intent: str
    reply: AssistantReply


def build_graph(llm_client: OpenAICompatibleClient):
    async def generate(state: ConversationState) -> dict:
        reply = await llm_client.reply(state["messages"], state["language_code"])
        return {"intent": reply.intent, "reply": reply}

    workflow = StateGraph(ConversationState)
    workflow.add_node("generate_response", generate)
    workflow.add_edge(START, "generate_response")
    workflow.add_edge("generate_response", END)
    return workflow.compile()
