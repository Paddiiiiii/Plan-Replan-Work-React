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
    "result_dir": BASE_DIR / "result",
    "result_geojson_dir": BASE_DIR / "result" / "geojson",
    "result_regions_dir": BASE_DIR / "result" / "regions",
    "result_llm_thinking_dir": BASE_DIR / "result" / "llm_thinking",
    "result_kg_graph_dir": BASE_DIR / "result" / "kg_graph"
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

# 历史结果展示配置（控制历史结果界面显示哪些内容）
HISTORY_DISPLAY_CONFIG = {
    "show_map": True,              # 显示地图
    "show_regions": True,          # 显示区域信息和筛选参数
    "show_llm_thinking": True,     # 显示LLM思考结果（KAG问答结果和LLM响应）
    "show_kg_graph": True          # 显示实体关系图
}

# 工具启用配置（控制哪些工具可以被调用）
TOOL_ENABLE_CONFIG = {
    "buffer_filter_tool": False,              # 缓冲区筛选工具
    "elevation_filter_tool": True,           # 高程筛选工具
    "slope_filter_tool": False,               # 坡度筛选工具
    "vegetation_filter_tool": False,          # 植被筛选工具
    "relative_position_filter_tool": True,   # 相对位置筛选工具
    "distance_filter_tool": True,            # 距离筛选工具
    "area_filter_tool": True                 # 面积筛选工具
}