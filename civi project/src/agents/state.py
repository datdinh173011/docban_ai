from typing import Annotated, TypedDict, List, Dict, Any
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # Chat message history
    messages: Annotated[List[AnyMessage], add_messages]
    
    # Original user input query
    query: str
    
    # Classification variables
    classification_step: int
    filters: Dict[str, Any]
    candidates: List[Dict[str, Any]]
    
    # Selected administrative procedure details
    selected_procedure: Dict[str, Any]
    
    # Retrieved chunks from ChromaDB
    retrieval_results: List[Dict[str, Any]]
    
    # Collected personal information for DOCX filling
    user_info: Dict[str, Any]
    
    # Dynamically generated questions from DOCX blank scanning
    form_questions: List[Dict[str, Any]]
    
    # Generated document path
    filled_form_path: str
    
    # Final response to user
    response: str
    
    # Optional bypass for direct RAG search
    direct_mode: bool
    
    # Intent classified by the Conversation Agent
    conversation_intent: str
    
    # 4 suggestions for the user to select from in the UI
    suggestions: List[str]
    
    # User's approval flag to initiate form filling
    fill_form_approved: bool
