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

EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"

RAG_CONFIG = {
    "top_k": 2,
    "oversample": 2,
    "min_k": 2,
    "max_distance": 0.35,
    "relaxed_distance_increment": 0.5,
    "w_sem": 0.75,
    "w_kw": 0.25,
    "metadata_boost_unit": 0.35,
    "metadata_boost_type": 0.10,
    "enable_tasks_collection": False,
    "enable_executions_collection": False,
    "similarity_threshold": 0.7
}
