import os
import json
from src.agents.llm import call_groq_llm

_CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'config')

def _load_prompt(filename):
    filepath = os.path.join(_CONFIG_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read().strip()


class ConversationAgent:
    """
    Main Conversation Agent — the primary interface with the user.
    
    Responsibilities:
    1. Understand what the user is saying (intent classification).
    2. Extract personal/technical information from natural conversation.
    3. Accumulate extracted info into user_info across multiple turns.
    4. Decide when enough info is collected and route to downstream agents.
    5. Generate friendly, natural Vietnamese responses.
    """

    def __init__(self):
        self.system_prompt = _load_prompt("conversation_prompt.txt")

    def run(self, state):
        messages = state.get("messages", [])
        if not messages:
            return {"response": "Xin chào! Tôi là CIVI, trợ lý hành chính công AI. Bạn cần giúp gì hôm nay?"}

        last_message = messages[-1].content

        # Build conversation history for context (last 10 messages)
        history = []
        recent_msgs = messages[-10:]
        for msg in recent_msgs:
            role = "user" if hasattr(msg, 'type') and msg.type == 'human' else "user"
            # Detect role from message class name
            class_name = type(msg).__name__
            if "Human" in class_name:
                role = "user"
            elif "AI" in class_name:
                role = "assistant"
            history.append({"role": role, "content": msg.content})

        # Include current user_info context so the LLM knows what's already collected
        user_info = state.get("user_info", {})
        collected_info_text = ""
        if user_info:
            collected_items = [f"  - {k}: {v}" for k, v in user_info.items() if v]
            collected_info_text = f"\n\nThông tin đã thu thập được từ các lượt trước:\n" + "\n".join(collected_items)

        # Include selected procedure context if any
        selected_proc = state.get("selected_procedure", {})
        proc_context = ""
        if selected_proc and selected_proc.get("name"):
            proc_context = f"\n\nThủ tục đã xác định: {selected_proc.get('name')} (Mã: {selected_proc.get('code', 'N/A')})"

        # Build the full system message with context
        full_system = self.system_prompt + collected_info_text + proc_context

        api_messages = [{"role": "system", "content": full_system}] + history

        raw_response = call_groq_llm(api_messages, temperature=0.3, max_tokens=1024)

        # Parse LLM JSON response
        try:
            data = json.loads(raw_response)
        except (json.JSONDecodeError, TypeError):
            # If the LLM didn't return valid JSON, treat it as a plain text response
            return {
                "response": raw_response,
                "conversation_intent": "other"
            }

        intent = data.get("intent", "other")
        extracted = data.get("extracted_info", {})
        friendly_response = data.get("friendly_response", "")
        suggestions = data.get("suggestions", [])

        # Merge newly extracted info into existing user_info (don't overwrite with null)
        updated_user_info = dict(user_info)  # copy existing
        for key, value in extracted.items():
            if value and value != "null" and str(value).strip():
                updated_user_info[key] = value

        # Detect approval for form filling
        fill_form_approved = state.get("fill_form_approved", False)
        if intent == "approve_form_filling" or last_message.strip().lower() in ("đồng ý điền đơn", "đồng ý", "có", "ok", "có điền đơn"):
            fill_form_approved = True

        # Build return state
        result = {
            "conversation_intent": intent,
            "user_info": updated_user_info,
            "response": friendly_response or raw_response,
            "query": last_message,  # Pass through for downstream RAG
            "suggestions": suggestions,
            "fill_form_approved": fill_form_approved
        }

        # If the user provided a procedure hint, store it for routing
        procedure_hint = extracted.get("procedure_hint")
        if procedure_hint and procedure_hint != "null":
            result["query"] = procedure_hint  # Use the hint as the RAG query

        return result
