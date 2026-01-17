import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

LLM_CONFIG = {
    "api_endpoint": "https://api.deepseek.com/v1/chat/completions",
    "api_key": "sk-667fd9da7e8049e6ac13a8d7eae93288",  # DeepSeek API Key
    "model": "deepseek-chat",
    "temperature": 0.7,
    "max_tokens": 8192,  # 增加到8192以确保JSON完整输出
    "top_p": 1.0,
    "n": 1,
    "stream": False,
    "timeout": 800,
    "rate_limit": {
        "rpm": 2000,  # 每分钟最大请求数
        "tpm": 500000  # 每分钟最大tokens数
    }
}

PATHS = {
    "data_dir": BASE_DIR / "data",
    "context_dir": BASE_DIR / "context",
    "static_context_dir": BASE_DIR / "context" / "static",
    "dynamic_context_dir": BASE_DIR / "context" / "dynamic",
    "kag_storage_dir": BASE_DIR / "context" / "dynamic" / "kag_storage",
    "result_dir": BASE_DIR / "result"
}

EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"

KAG_CONFIG = {
    "top_k": 2,
    "oversample": 2,
    "min_k": 2,
    "max_distance": 0.35,
    "relaxed_distance_increment": 0.5,
    "w_sem": 0.75,
    "w_kw": 0.25,
    "metadata_boost_unit": 0.35,
    "metadata_boost_type": 0.10,
    "use_llm_reasoning": False,
    "use_openspg": True,
    "kg_storage_path": str(PATHS["kag_storage_dir"]),
    "embedding_model": EMBEDDING_MODEL
}

RAG_CONFIG = KAG_CONFIG

# 地理边界限制（经纬度范围）
GEO_BOUNDS = {
    "min_lon": 118.0,  # 西经
    "max_lon": 119.0,  # 东经
    "min_lat": 31.0,   # 南纬
    "max_lat": 32.0    # 北纬
}