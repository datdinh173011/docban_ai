import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# Load LangGraph pipeline and message classes
from src.agents.graph import graph
from langchain_core.messages import HumanMessage, AIMessage

# Load dotenv config
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(
    title="CIVI AI Agent - Public Administration API Backend",
    description="API Backend hỗ trợ tra cứu thủ tục hành chính công và điền mẫu đơn tự động.",
    version="1.0.0"
)

# Enable CORS for frontend widgets or portal integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pydantic Schemas ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., description="Vai trò: 'user' hoặc 'assistant'")
    content: str = Field(..., description="Nội dung tin nhắn")

class ChatRequest(BaseModel):
    message: str = Field(..., description="Tin nhắn mới của người dùng")
    history: List[ChatMessage] = Field(default=[], description="Lịch sử cuộc hội thoại")
    user_info: Dict[str, Any] = Field(default={}, description="Thông tin cá nhân đã thu thập")
    selected_procedure: Dict[str, Any] = Field(default={}, description="Thủ tục hiện tại đang được chọn")
    form_questions: List[Dict[str, Any]] = Field(default=[], description="Danh sách các câu hỏi điền đơn hiện tại")
    fill_form_approved: bool = Field(default=False, description="Trạng thái người dùng phê duyệt điền đơn")

class ChatResponse(BaseModel):
    response: str = Field(..., description="Câu trả lời của trợ lý ảo")
    history: List[ChatMessage] = Field(..., description="Lịch sử hội thoại đã cập nhật")
    user_info: Dict[str, Any] = Field(..., description="Thông tin cá nhân đã cập nhật")
    selected_procedure: Dict[str, Any] = Field(..., description="Thông tin thủ tục được chọn")
    form_questions: List[Dict[str, Any]] = Field(..., description="Danh sách câu hỏi điền đơn cập nhật")
    fill_form_approved: bool = Field(..., description="Trạng thái phê duyệt điền đơn cập nhật")
    suggestions: List[str] = Field(..., description="4 gợi ý lựa chọn cho người dùng click nhanh")
    filled_form_download_url: Optional[str] = Field(None, description="Đường dẫn tải xuống file đơn đã điền (nếu có)")

# ─── Endpoints ─────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "CIVI AI Administrative Public API",
        "endpoints": {
            "/api/chat": "POST - Gửi tin nhắn và cập nhật trạng thái hội thoại",
            "/api/download": "GET - Tải xuống file đơn Word đã điền hoàn thành"
        }
    }

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Convert simple history schema to LangChain message classes
        messages = []
        for msg in request.history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            else:
                messages.append(AIMessage(content=msg.content))
        
        # Append the new user message
        messages.append(HumanMessage(content=request.message))
        
        # Build the LangGraph initial state
        initial_state = {
            "messages": messages,
            "query": request.message,
            "classification_step": 1,
            "filters": {},
            "candidates": [],
            "selected_procedure": request.selected_procedure,
            "retrieval_results": [],
            "user_info": request.user_info,
            "form_questions": request.form_questions,
            "filled_form_path": "",
            "response": "",
            "direct_mode": False,
            "conversation_intent": "",
            "suggestions": [],
            "fill_form_approved": request.fill_form_approved
        }
        
        # Invoke the LangGraph agentic workflow
        output_state = graph.invoke(initial_state)
        
        # Convert updated messages back to simple API structure
        updated_history = []
        for m in output_state.get("messages", []):
            role = "user" if "Human" in type(m).__name__ else "assistant"
            updated_history.append(ChatMessage(role=role, content=m.content))
            
        # Determine if a download link is ready
        filled_form_path = output_state.get("filled_form_path", "")
        download_url = None
        if filled_form_path and os.path.exists(filled_form_path):
            filename = os.path.basename(filled_form_path)
            download_url = f"/api/download?filename={filename}"
            
        return ChatResponse(
            response=output_state.get("response", ""),
            history=updated_history,
            user_info=output_state.get("user_info", {}),
            selected_procedure=output_state.get("selected_procedure", {}),
            form_questions=output_state.get("form_questions", []),
            fill_form_approved=output_state.get("fill_form_approved", False),
            suggestions=output_state.get("suggestions", []),
            filled_form_download_url=download_url
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống trong quá trình xử lý: {str(e)}")

@app.get("/api/download")
def download_endpoint(filename: str):
    output_dir = "output"
    file_path = os.path.join(output_dir, filename)
    
    # Security check: prevent directory traversal attacks
    abs_path = os.path.abspath(file_path)
    abs_output_dir = os.path.abspath(output_dir)
    if not abs_path.startswith(abs_output_dir):
        raise HTTPException(status_code=400, detail="Tên tệp tin không hợp lệ.")
        
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File không tồn tại hoặc đã bị xóa.")
        
    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )

if __name__ == "__main__":
    uvicorn.run("main_api:app", host="0.0.0.0", port=8000, reload=True)
