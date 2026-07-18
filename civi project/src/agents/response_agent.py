import os
import json
from src.agents.llm import call_groq_llm
from src.ingestion.metadata_loader import MetadataLoader

# Load prompt from external config file
_CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'config')

def _load_prompt(filename):
    filepath = os.path.join(_CONFIG_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read().strip()

class ResponseAgent:
    def __init__(self):
        self.metadata_loader = MetadataLoader()

    def run(self, state):
        query = state.get("query", "")
        selected_proc = state.get("selected_procedure", {})
        results = state.get("retrieval_results", [])
        
        # In direct search mode, dynamically identify selected procedure from the best RAG match
        if (not selected_proc or "code" not in selected_proc) and results:
            best_match = results[0]["metadata"]
            selected_proc = {
                "id": best_match.get("code"),
                "code": best_match.get("code"),
                "name": best_match.get("title"),
                "co_quan_thuc_hien": best_match.get("co_quan_thuc_hien") or "Ủy ban nhân dân cấp huyện",
                "cap_thuc_hien": best_match.get("cap_thuc_hien")
            }
            
        # Merge all retrieved texts
        retrieved_text = "\n\n---\n\n".join([f"Source: {r['metadata'].get('section', 'General')}\n{r['text']}" for r in results])
        
        # Get matching form templates details
        form_templates_info = ""
        has_forms = False
        if selected_proc and "code" in selected_proc:
            forms = self.metadata_loader.get_forms_for_procedure(selected_proc["code"])
            if forms:
                has_forms = True
                form_templates_info = "\n\nCác mẫu đơn/tờ khai điền sẵn đi kèm:\n"
                for f in forms:
                    form_templates_info += f"- **{f.get('FileName')}**: {f.get('ComponentName')}\n"
        
        # Load system prompt from external config file
        system_prompt = _load_prompt("response_prompt.txt")
        
        user_prompt = f"""
        Thủ tục: {selected_proc.get('name', 'Thủ tục hành chính')} (Mã số: {selected_proc.get('code', 'N/A')})
        Cơ quan thực hiện: {selected_proc.get('co_quan_thuc_hien', 'N/A')}
        
        Tài liệu nguồn trích xuất:
        {retrieved_text}
        {form_templates_info}
        
        Câu hỏi người dùng: {query}
        """
        
        api_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = call_groq_llm(api_messages, temperature=0.2)
        
        # Append proposal and setup suggestions if form templates exist
        suggestions = state.get("suggestions", [])
        if has_forms:
            response += "\n\n---\n\n💡 **Tôi có thể hỗ trợ bạn điền đơn mẫu biểu tự động cho thủ tục này.**\n\n👉 **Bạn có muốn tiến hành điền đơn tự động không?**"
            suggestions = ["Đồng ý điền đơn", "Không, cảm ơn"]
        
        # Save response and dynamically matched selected procedure in state
        return {
            "response": response,
            "selected_procedure": selected_proc,
            "suggestions": suggestions,
            "fill_form_approved": False  # Reset/wait for user approval
        }
