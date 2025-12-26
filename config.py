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

# RAG配置：统一使用cosine距离度量
# max_distance: cosine距离阈值，distance越小越相似，distance = 1 - cosine_similarity
# 例如 max_distance=0.35 相当于相似度 >= 0.65
RAG_CONFIG = {
    "top_k": 3,                    # 最终返回的top_k结果数
    "oversample": 3,               # 向量召回时先召回 top_k * oversample 条候选
    "min_k": 2,                    # 过滤后最少保留的结果数，不足则降级策略
    "max_distance": 0.35,          # cosine距离阈值（相当于相似度 >= 0.65）
    "w_sem": 0.75,                 # 语义相似度权重（融合打分用）
    "w_kw": 0.25,                  # 关键词匹配权重（融合打分用）
    "metadata_boost_unit": 0.15,   # unit匹配时的metadata加分
    "metadata_boost_type": 0.10,   # type匹配时的metadata加分
    "similarity_threshold": 0.7    # 保留旧字段以兼容，实际使用max_distance
}
