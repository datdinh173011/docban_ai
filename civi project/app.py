import os
import sys

# Monkeypatch sys.stdout.flush to prevent ValueError: I/O operation on closed file from tqdm
original_flush = getattr(sys.stdout, 'flush', None)
def safe_flush():
    try:
        if original_flush:
            original_flush()
    except ValueError:
        pass
sys.stdout.flush = safe_flush

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage
from src.agents.graph import graph
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()

# Page configuration with custom tab title and icon
st.set_page_config(
    page_title="CIVI AI Agent - Trợ lý Hành chính Công",
    page_icon="💬",
    layout="wide"
)

# Custom Sleek CSS for premium dark-themed styling
st.markdown("""
<style>
    /* Styling headers and main app */
    .stApp {
        background-color: #0e1117;
        color: #e0e0e0;
    }
    
    /* Center title and logo */
    .app-header {
        text-align: center;
        padding: 20px 0;
        background: linear-gradient(135deg, #1f4037, #99f2c8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 800;
        margin-bottom: 5px;
    }
    
    .app-subtitle {
        text-align: center;
        color: #888888;
        font-size: 1.1rem;
        margin-bottom: 30px;
    }
    
    /* Custom style for sidebar */
    [data-testid="stSidebar"] {
        background-color: #161920 !important;
        border-right: 1px solid #2d3139;
    }
    
    /* Clean chat message borders */
    .stChatMessage {
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
        border: 1px solid #2d3139;
    }
    
    /* Style candidates and stats card */
    .status-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Main title
st.markdown('<div class="app-header">CIVI AI AGENT</div>', unsafe_allow_html=True)
st.markdown('<div class="app-subtitle">Hệ thống Trợ lý Hành chính Công Đa nhiệm (Phase 1)</div>', unsafe_allow_html=True)

# 1. Initialize State in Streamlit Session
if "agent_state" not in st.session_state:
    st.session_state.agent_state = {
        "messages": [],
        "query": "",
        "classification_step": 1,
        "filters": {},
        "candidates": [],
        "selected_procedure": {},
        "retrieval_results": [],
        "user_info": {},
        "form_questions": [],
        "filled_form_path": "",
        "response": "",
        "direct_mode": False,
        "conversation_intent": "",
        "suggestions": ["Tôi muốn xây dựng nhà ở", "Tôi muốn đăng ký đất đai", "Tôi muốn chuyển nhượng nhà đất", "Tôi muốn hỏi thông tin thủ tục"],
        "fill_form_approved": False
    }
    
    # Add initial greeting message
    greeting_text = "Xin chào! Tôi là CIVI, trợ lý hành chính công. Bạn đang cần giải quyết thủ tục gì hôm nay?"
    st.session_state.agent_state["messages"].append(AIMessage(content=greeting_text))
    st.session_state.agent_state["response"] = greeting_text

agent_state = st.session_state.agent_state

# 2. Sidebar configuration and debug parameters
with st.sidebar:
    st.markdown("### 🛠️ Trạng thái & Debug")
    
    # Reset Chat button
    if st.button("🔄 Đặt lại hội thoại", use_container_width=True):
        st.session_state.agent_state = {
            "messages": [],
            "query": "",
            "classification_step": 1,
            "filters": {},
            "candidates": [],
            "selected_procedure": {},
            "retrieval_results": [],
            "user_info": {},
            "form_questions": [],
            "filled_form_path": "",
            "response": "",
            "direct_mode": False,
            "conversation_intent": "",
            "suggestions": ["Tôi muốn xây dựng nhà ở", "Tôi muốn đăng ký đất đai", "Tôi muốn chuyển nhượng nhà đất", "Tôi muốn hỏi thông tin thủ tục"],
            "fill_form_approved": False
        }
        greeting_text = "Xin chào! Tôi có thể giúp gì cho bạn hôm nay?"
        st.session_state.agent_state["messages"].append(AIMessage(content=greeting_text))
        st.session_state.agent_state["response"] = greeting_text
        st.rerun()

    st.markdown("---")
    
    # Display conversation intent
    intent = agent_state.get("conversation_intent", "")
    if intent:
        intent_labels = {
            "greeting": "👋 Chào hỏi",
            "new_procedure": "🔍 Đang tìm hiểu nhu cầu...",
            "confirmed_procedure": "✅ Đã xác định thủ tục",
            "ask_info": "❓ Hỏi thông tin",
            "provide_info": "📝 Cung cấp thông tin",
            "thanks": "🙏 Cảm ơn",
            "other": "💬 Hội thoại chung"
        }
        st.markdown(f"**Ý định:** {intent_labels.get(intent, intent)}")
    
    # Display collected user info
    user_info = agent_state.get("user_info", {})
    filled_items = {k: v for k, v in user_info.items() if v and v != "null"}
    if filled_items:
        st.markdown("**📋 Thông tin đã thu thập:**")
        for k, v in filled_items.items():
            st.markdown(f"- `{k}`: {v}")
    
    # Display selected procedure
    sel_proc = agent_state.get("selected_procedure", {})
    if sel_proc and sel_proc.get("code"):
        st.markdown("---")
        st.markdown("🎯 **Thủ tục đã xác định:**")
        st.success(f"**{sel_proc.get('code', 'N/A')}**\n\n{sel_proc.get('name', 'N/A')}")

    # File downloader if form is filled
    form_path = agent_state.get("filled_form_path", "")
    if form_path and os.path.exists(form_path):
        st.markdown("---")
        st.markdown("### 📄 Đơn mẫu biểu đã điền")
        try:
            with open(form_path, "rb") as f:
                file_bytes = f.read()
            st.download_button(
                label="📥 Tải xuống đơn mẫu biểu (.docx)",
                data=file_bytes,
                file_name=os.path.basename(form_path),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
            st.success("Đã tự động điền đơn thành công!")
        except Exception as e:
            st.error(f"Lỗi tải file: {e}")

# 3. Main Chat View
# Display existing messages
for msg in agent_state["messages"]:
    role = "user" if isinstance(msg, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.markdown(msg.content)

# Render suggestions/options if present
clicked_suggestion = None
suggestions = agent_state.get("suggestions", [])
if suggestions:
    st.write("💡 **Gợi ý lựa chọn:**")
    cols = st.columns(len(suggestions))
    for idx, sugg in enumerate(suggestions):
        with cols[idx]:
            if st.button(sugg, key=f"sugg_btn_{idx}_{sugg[:12]}", use_container_width=True):
                clicked_suggestion = sugg

# Accept user input (either via text box or suggestion click)
user_input = None
if clicked_suggestion:
    user_input = clicked_suggestion
elif txt_input := st.chat_input("Nhập câu hỏi của bạn tại đây..."):
    user_input = txt_input

if user_input:
    # Render user message immediately
    with st.chat_message("user"):
        st.markdown(user_input)
        
    # Update local and session state
    agent_state["messages"].append(HumanMessage(content=user_input))
    agent_state["query"] = user_input
    
    # Process with the LangGraph agent
    with st.chat_message("assistant"):
        with st.spinner("CIVI đang suy nghĩ..."):
            try:
                # Invoke the LangGraph workflow
                output_state = graph.invoke(agent_state)
                # Update agent state
                agent_state.update(output_state)
                # Render response
                st.markdown(agent_state["response"])
                # Save assistant response to session messages
                agent_state["messages"].append(AIMessage(content=agent_state["response"]))
                # Trigger a rerun to update the sidebar values (candidates, filled form, etc.)
                st.rerun()
            except Exception as e:
                st.error(f"Đã xảy ra lỗi trong quá trình xử lý: {e}")
