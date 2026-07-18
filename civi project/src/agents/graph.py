from langgraph.graph import StateGraph, END
from src.agents.state import AgentState
from src.agents.conversation_agent import ConversationAgent
from src.agents.retrieval_agent import RetrievalAgent
from src.agents.response_agent import ResponseAgent
from src.agents.form_filling_agent import FormFillingAgent

# Instantiate agents
conversation_agent = ConversationAgent()
retrieval_agent = RetrievalAgent()
resp_agent = ResponseAgent()
form_filling_agent = FormFillingAgent()

# ─── Node functions ───────────────────────────────────────────────

def conversation_node(state):
    return conversation_agent.run(state)

def retrieval_node(state):
    return retrieval_agent.run(state)

def response_node(state):
    return resp_agent.run(state)

def form_filling_node(state):
    return form_filling_agent.run(state)

# ─── Build Graph ──────────────────────────────────────────────────

workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("conversation", conversation_node)
workflow.add_node("retrieval", retrieval_node)
workflow.add_node("response", response_node)
workflow.add_node("form_filling", form_filling_node)

# ─── Entry Point: Conversation Agent is ALWAYS first ──────────────

workflow.set_entry_point("conversation")

# ─── Routing from Conversation Agent ─────────────────────────────

def route_conversation(state):
    """
    Decide next node from Conversation Agent:
    - confirmed_procedure / ask_info  →  retrieval (go search instructions)
    - approve_form_filling / provide_info (if approved)  →  form_filling
    - greeting / thanks / other / new_procedure  →  END
    """
    intent = state.get("conversation_intent", "other")
    fill_approved = state.get("fill_form_approved", False)
    
    if intent in ("confirmed_procedure", "ask_info"):
        return "retrieval"
    elif intent == "approve_form_filling" or fill_approved:
        selected_proc = state.get("selected_procedure", {})
        if selected_proc and selected_proc.get("code"):
            from src.ingestion.metadata_loader import MetadataLoader
            loader = MetadataLoader()
            forms = loader.get_forms_for_procedure(selected_proc["code"])
            if forms:
                return "form_filling"
        return "__end__"
    else:
        return "__end__"

workflow.add_conditional_edges(
    "conversation",
    route_conversation,
    {
        "__end__": END,
        "retrieval": "retrieval",
        "form_filling": "form_filling"
    }
)

# ─── Retrieval → Response ─────────────────────────────────────────

workflow.add_edge("retrieval", "response")

# ─── Response → END (Always stop to let the user review guidelines) ─

workflow.add_edge("response", END)

# ─── Form Filling → END ──────────────────────────────────────────

workflow.add_edge("form_filling", END)

# ─── Compile ──────────────────────────────────────────────────────

graph = workflow.compile()
