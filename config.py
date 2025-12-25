import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

LLM_CONFIG = {
    "api_endpoint": "http://192.168.1.200:11434/v1/chat/completions",
    "model": "qwen3:32b",
    "temperature": 0.7,
    "max_tokens": 4096,
    "top_p": 1.0,
    "n": 1,
    "stream": False,
    "timeout": 180
}

PATHS = {
    "data_dir": BASE_DIR / "data",
    "context_dir": BASE_DIR / "context",
    "static_context_dir": BASE_DIR / "context" / "static",
    "dynamic_context_dir": BASE_DIR / "context" / "dynamic",
    "chroma_db_dir": BASE_DIR / "context" / "dynamic" / "chroma_db",
    "result_dir": BASE_DIR / "result"
}

CHROMA_CONFIG = {
    "persist_directory": str(PATHS["chroma_db_dir"]),
    "collection_tasks": "tasks",
    "collection_executions": "executions",
    "collection_knowledge": "knowledge",
    "collection_equipment": "equipment"
}

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

RAG_CONFIG = {
    "top_k": 5,
    "similarity_threshold": 0.7
}
