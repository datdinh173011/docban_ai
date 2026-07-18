import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
    GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    DATA_DIR = os.getenv("DATA_DIR", "./dichvucong_xay_dung_crawled_2026-07-17")
    
    # Embedding model name for local sentence-transformers
    EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
