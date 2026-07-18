import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from src.agents.graph import graph

# Ensure utf-8 output on Windows
if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

console = Console()

def print_welcome_message():
    welcome_text = """
    ========================================================================
     CIVI AI AGENT: HỆ THỐNG TRỢ LÝ HÀNH CHÍNH CÔNG ĐA NHIỆM (PHASE 1 - RAG)
    ========================================================================
    Sử dụng LangGraph + Groq LLM + Docling PDF Parser + local ChromaDB
    
    * Tra cứu nhanh thủ tục hành chính
    * Phân loại tự động theo cây hỏi 7 bước (Excel)
    * Trả kết quả chuẩn: Trình tự, Cách thức thực hiện, Thành phần hồ sơ
    * Tự động điền đơn mẫu biểu DOCX
    ========================================================================
    Gõ '/exit' để thoát, '/reset' để đặt lại cuộc hội thoại.
    """
    console.print(Panel(welcome_text, title="CIVI AI Agent", style="bold green"))

def main():
    print_welcome_message()
    
    # Initialize Agent State
    state = {
        "messages": [],
        "query": "",
        "classification_step": 1,
        "filters": {},
        "candidates": [],
        "selected_procedure": {},
        "retrieval_results": [],
        "user_info": {},
        "filled_form_path": "",
        "response": ""
    }
    
    # Add initial greeting message
    greeting = "Xin chào! Tôi là CIVI, trợ lý hành chính công. Bạn đang cần giải quyết thủ tục gì hôm nay?"
    console.print(f"\n[bold green]CIVI:[/bold green] {greeting}")
    
    # Track messages history for state
    from langchain_core.messages import AIMessage, HumanMessage
    state["messages"].append(AIMessage(content=greeting))
    
    while True:
        try:
            user_input = console.input("\n[bold blue]Bạn:[/bold blue] ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() == "/exit":
                console.print("[bold red]Tạm biệt![/bold red]")
                break
                
            if user_input.lower() == "/reset":
                # Clear state
                state = {
                    "messages": [],
                    "query": "",
                    "classification_step": 1,
                    "filters": {},
                    "candidates": [],
                    "selected_procedure": {},
                    "retrieval_results": [],
                    "user_info": {},
                    "filled_form_path": "",
                    "response": ""
                }
                console.print("[bold yellow]Đã đặt lại cuộc hội thoại.[/bold yellow]")
                greeting = "Xin chào! Tôi có thể giúp gì cho bạn hôm nay?"
                console.print(f"\n[bold green]CIVI:[/bold green] {greeting}")
                state["messages"].append(AIMessage(content=greeting))
                continue
            
            # Update state with the user message
            state["messages"].append(HumanMessage(content=user_input))
            state["query"] = user_input
            
            # Execute one step in the LangGraph workflow
            console.print("[italic dim]CIVI đang suy nghĩ...[/italic dim]")
            output_state = graph.invoke(state)
            
            # Update local state with the returned state from graph
            state.update(output_state)
            
            # Get latest response
            response_text = state.get("response", "Không nhận được phản hồi.")
            
            # Print response using Rich markdown
            console.print("\n[bold green]CIVI:[/bold green]")
            console.print(Markdown(response_text))
            
            # Save the response as AIMessage
            state["messages"].append(AIMessage(content=response_text))
            
        except KeyboardInterrupt:
            console.print("\n[bold red]Tạm biệt![/bold red]")
            break
        except Exception as e:
            console.print(f"\n[bold red]Đã xảy ra lỗi:[/bold red] {e}")

if __name__ == "__main__":
    main()
