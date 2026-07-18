import os
import json
from src.agents.llm import call_groq_llm

# Load prompt from external config file
_CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'config')

def _load_prompt(filename):
    filepath = os.path.join(_CONFIG_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read().strip()

def router_node(state):
    """
    Router Agent: Classifies the user's intent.
    Reads system prompt from config/router_prompt.txt for easy customization.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"current_agent": "router"}
        
    last_user_message = messages[-1].content
    
    # If direct_mode is active or query starts with '?', route directly to RAG search
    if state.get("direct_mode") or last_user_message.strip().startswith("?"):
        query_text = last_user_message.strip().lstrip("?")
        return {
            "query": query_text,
            "response": "direct_question",
            "selected_procedure": {}
        }
    
    # Load system prompt from external config file
    system_prompt = _load_prompt("router_prompt.txt")
    
    api_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": last_user_message}
    ]
    
    response = call_groq_llm(api_messages, temperature=0.0)
    
    try:
        data = json.loads(response)
        intent = data.get("intent", "direct_question")
    except Exception:
        intent = "direct_question"
        
    return {
        "query": last_user_message,
        "response": intent
    }
