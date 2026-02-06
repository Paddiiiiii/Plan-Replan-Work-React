# -*- coding: utf-8 -*-
"""
知识抽取交互式前端
支持输入文本并实时进行知识抽取，展示抽取过程和结果

使用方法:
    python -m streamlit run kag_extraction_frontend.py --server.port 9501 --server.address=0.0.0.0
    
    注意: 
    - 默认端口已配置为9501（避免与外层系统的8501冲突）
    - 已配置允许局域网访问（0.0.0.0）
    - 页面会自动重定向到127.0.0.1:9501（本机访问）
"""
import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
import json
import time
import uuid
import datetime

# 检查是否使用streamlit run启动
if __name__ == "__main__" and "streamlit" not in sys.modules:
    print("=" * 60)
    print("错误: 请使用 streamlit 命令启动此应用")
    print("=" * 60)
    print("\n正确的启动方式:")
    print("  python -m streamlit run kag_extraction_frontend.py --server.port 9501 --server.address=0.0.0.0")
    print("\n  注意: 默认端口已配置为9501（避免与外层系统的8501冲突），已配置允许局域网访问")
    print("        页面会自动重定向到127.0.0.1:9501（本机访问）")
    print("=" * 60)
    sys.exit(1)

import streamlit as st

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 设置页面配置
st.set_page_config(
    page_title="知识抽取系统",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


# 注入自定义CSS样式
st.markdown("""
<style>
    /* 全局页面背景 */
    html, body, #root, .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #5a67d8 100%) !important;
        background-attachment: fixed !important;
        min-height: 100vh !important;
    }
    
    /* 主容器样式 */
    .main {
        background: transparent !important;
        padding: 2rem;
    }
    
    /* Streamlit主内容区 */
    .block-container {
        background: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(10px) !important;
        border-radius: 20px !important;
        padding: 2rem !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1) !important;
    }
    
    /* 主内容区文本 */
    .block-container p, 
    .block-container div, 
    .block-container span {
        color: #f7fafc !important;
    }
    
    /* 所有Streamlit元素容器 */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #5a67d8 100%) !important;
    }
    
    [data-testid="stHeader"] {
        background: rgba(102, 126, 234, 0.8) !important;
        backdrop-filter: blur(10px) !important;
    }
    
    /* 标签页样式 */
    [data-baseweb="tabs"] {
        background: rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
        padding: 0.5rem !important;
    }
    
    [data-baseweb="tab"] {
        color: rgba(255, 255, 255, 0.8) !important;
        border-radius: 8px !important;
    }
    
    [data-baseweb="tab"]:hover {
        background: rgba(255, 255, 255, 0.2) !important;
        color: white !important;
    }
    
    [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
    }
    
    /* 标题样式 */
    h1 {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #5a67d8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 3rem !important;
        font-weight: 800 !important;
        text-align: center;
        margin-bottom: 1rem !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    
    /* 卡片样式 */
    .stCard {
        background: rgba(255, 255, 255, 0.12) !important;
        border-radius: 20px !important;
        padding: 1.5rem !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2) !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
        backdrop-filter: blur(10px) !important;
        transition: transform 0.3s ease, box-shadow 0.3s ease !important;
    }
    
    /* 卡片内文本 */
    .stCard p, .stCard div, .stCard span {
        color: #f7fafc !important;
    }
    
    .stCard:hover {
        transform: translateY(-5px) !important;
        box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* 按钮样式 */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #5a67d8 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6) !important;
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%) !important;
    }
    
    /* 文本区域样式 */
    .stTextArea > div > div > textarea {
        background: rgba(255, 255, 255, 0.85) !important;
        border-radius: 12px !important;
        border: 2px solid rgba(102, 126, 234, 0.5) !important;
        padding: 1rem !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
        color: #2d3748 !important;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2) !important;
        background: rgba(255, 255, 255, 0.95) !important;
    }
    
    /* 标签样式 */
    label {
        color: #ffffff !important;
        font-weight: 600 !important;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* 标题颜色 - 保持渐变效果 */
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* 普通文本颜色 */
    p, div, span {
        color: #f7fafc !important;
    }
    
    /* 深色文本区域 */
    .stMarkdown p, .stMarkdown div, .stMarkdown span {
        color: #f7fafc !important;
    }
    
    /* 指标标签颜色 */
    [data-testid="stMetricLabel"] {
        color: rgba(255, 255, 255, 0.95) !important;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2) !important;
    }
    
    /* 指标值颜色 - 保持渐变效果 */
    [data-testid="stMetricValue"] {
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* 侧边栏样式 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
    }
    
    [data-testid="stSidebar"] .stButton > button {
        background: rgba(255, 255, 255, 0.2) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
    }
    
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255, 255, 255, 0.3) !important;
    }
    
    /* 指标卡片样式 */
    [data-testid="stMetricValue"] {
        font-size: 2.5rem !important;
        font-weight: 700 !important;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 1rem !important;
        color: #666 !important;
        font-weight: 500 !important;
    }
    
    /* 进度条样式 */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%) !important;
        border-radius: 10px !important;
    }
    
    /* 展开器样式 */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.15) !important;
        border-radius: 10px !important;
        padding: 0.75rem 1rem !important;
        font-weight: 600 !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        color: #ffffff !important;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3) !important;
    }
    
    .streamlit-expanderHeader:hover {
        background: rgba(255, 255, 255, 0.25) !important;
    }
    
    .streamlit-expanderContent {
        background: rgba(255, 255, 255, 0.08) !important;
        border-radius: 10px !important;
        margin-top: 0.5rem !important;
        color: #f7fafc !important;
    }
    
    .streamlit-expanderContent p, 
    .streamlit-expanderContent div, 
    .streamlit-expanderContent span {
        color: #f7fafc !important;
    }
    
    /* 信息框样式 */
    .stAlert {
        border-radius: 12px !important;
        border-left: 4px solid #667eea !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
        background: rgba(255, 255, 255, 0.15) !important;
        backdrop-filter: blur(10px) !important;
    }
    
    .stAlert p, .stAlert div {
        color: #ffffff !important;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* JSON查看器样式 */
    [data-testid="stJson"] {
        background: rgba(30, 30, 30, 0.8) !important;
        border-radius: 8px !important;
        padding: 1rem !important;
    }
    
    /* 下载按钮容器 */
    [data-testid="stDownloadButton"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    }
    
    /* 代码块样式 */
    .stCodeBlock {
        background: #1e1e1e !important;
        border-radius: 8px !important;
        padding: 1rem !important;
    }
    
    /* 动画效果 */
    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .fade-in {
        animation: fadeIn 0.5s ease-out;
    }
    
    @keyframes pulse {
        0%, 100% {
            opacity: 1;
        }
        50% {
            opacity: 0.7;
        }
    }
    
    .pulse {
        animation: pulse 2s ease-in-out infinite;
    }
    
    @keyframes shimmer {
        0% {
            background-position: -1000px 0;
        }
        100% {
            background-position: 1000px 0;
        }
    }
    
    .shimmer {
        background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%);
        background-size: 1000px 100%;
        animation: shimmer 3s infinite;
    }
    
    /* 加载动画 */
    @keyframes spin {
        from {
            transform: rotate(0deg);
        }
        to {
            transform: rotate(360deg);
        }
    }
    
    .spinning {
        animation: spin 2s linear infinite;
    }
    
    /* Multiselect下拉框样式 */
    [data-baseweb="select"] {
        background: rgba(255, 255, 255, 0.15) !important;
        border-radius: 8px !important;
    }
    
    [data-baseweb="select"] > div {
        background: rgba(255, 255, 255, 0.15) !important;
        color: #f7fafc !important;
    }
    
    /* Multiselect下拉框选项样式 - 强制白色背景和深色文字 */
    [data-baseweb="popover"] {
        background: #ffffff !important;
        backdrop-filter: blur(10px) !important;
        border-radius: 8px !important;
    }
    
    [data-baseweb="menu"] {
        background: #ffffff !important;
    }
    
    [data-baseweb="menu"] ul {
        background: #ffffff !important;
    }
    
    [data-baseweb="menu"] li {
        background: #ffffff !important;
        color: #1a1a1a !important;
    }
    
    /* 强制所有下拉选项文字为黑色 */
    [data-baseweb="menu"] li *,
    [data-baseweb="menu"] li span,
    [data-baseweb="menu"] li div,
    [data-baseweb="menu"] li label,
    [data-baseweb="menu"] li p {
        color: #1a1a1a !important;
        background: transparent !important;
    }
    
    [data-baseweb="menu"] li:hover {
        background: rgba(102, 126, 234, 0.2) !important;
    }
    
    [data-baseweb="menu"] li:hover *,
    [data-baseweb="menu"] li:hover span,
    [data-baseweb="menu"] li:hover div,
    [data-baseweb="menu"] li:hover label {
        color: #1a1a1a !important;
    }
    
    [data-baseweb="menu"] li[aria-selected="true"] {
        background: rgba(102, 126, 234, 0.3) !important;
    }
    
    [data-baseweb="menu"] li[aria-selected="true"] *,
    [data-baseweb="menu"] li[aria-selected="true"] span,
    [data-baseweb="menu"] li[aria-selected="true"] div,
    [data-baseweb="menu"] li[aria-selected="true"] label {
        color: #1a1a1a !important;
    }
    
    /* 确保所有文本元素都是深色 */
    [data-baseweb="popover"] * {
        color: #1a1a1a !important;
    }
    
    [data-baseweb="popover"] span,
    [data-baseweb="popover"] div,
    [data-baseweb="popover"] p,
    [data-baseweb="popover"] label {
        color: #1a1a1a !important;
    }
    
    /* Multiselect标签样式 */
    [data-baseweb="tag"] {
        background: rgba(102, 126, 234, 0.3) !important;
        color: #f7fafc !important;
        border: 1px solid rgba(102, 126, 234, 0.5) !important;
    }
    
    /* Multiselect输入框文本颜色 */
    [data-baseweb="select"] input,
    [data-baseweb="select"] span {
        color: #f7fafc !important;
    }
    
    /* Multiselect占位符文本 */
    [data-baseweb="select"] input::placeholder {
        color: rgba(247, 250, 252, 0.6) !important;
    }
    
    /* 成功/错误/警告消息样式 */
    .stSuccess {
        background: linear-gradient(135deg, rgba(76, 175, 80, 0.1) 0%, rgba(76, 175, 80, 0.2) 100%) !important;
        border-left: 4px solid #4caf50 !important;
    }
    
    .stError {
        background: linear-gradient(135deg, rgba(244, 67, 54, 0.1) 0%, rgba(244, 67, 54, 0.2) 100%) !important;
        border-left: 4px solid #f44336 !important;
    }
    
    .stWarning {
        background: linear-gradient(135deg, rgba(255, 152, 0, 0.1) 0%, rgba(255, 152, 0, 0.2) 100%) !important;
        border-left: 4px solid #ff9800 !important;
    }
    
    /* 分隔线样式 */
    hr {
        border: none !important;
        height: 2px !important;
        background: linear-gradient(90deg, transparent 0%, #667eea 50%, transparent 100%) !important;
        margin: 2rem 0 !important;
    }
    
    /* 滚动条样式 */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(0, 0, 0, 0.1);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }
</style>
""", unsafe_allow_html=True)

# 导入配置模块
from kag.common.conf import KAG_CONFIG
from kag.common.registry import import_modules_from_path
from kag.interface import ExtractorABC, LLMClient
from kag.builder.model.chunk import Chunk, ChunkTypeEnum
from kag.builder.model.sub_graph import SubGraph
try:
    from kag.builder.model.node import Node
    from kag.builder.model.edge import Edge
except ImportError:
    # 如果导入失败，使用interface中的定义
    from kag.interface.common.model.sub_graph import Node, Edge
from kag.builder.component.reader.enhanced_graph_visualizer import visualize_enhanced_graph


# 初始化会话状态
if 'extractor' not in st.session_state:
    st.session_state.extractor = None
if 'extraction_history' not in st.session_state:
    st.session_state.extraction_history = []
if 'current_result' not in st.session_state:
    st.session_state.current_result = None


@st.cache_resource
def init_extractor():
    """初始化抽取器（缓存）"""
    try:
        # 获取项目路径
        project_path = Path(__file__).parent
        
        # 切换到项目目录
        original_cwd = os.getcwd()
        os.chdir(str(project_path))
        
        try:
            # 初始化配置
            config_file = project_path / "kag_config.yaml"
            if not config_file.exists():
                st.error(f"配置文件不存在: {config_file}")
                return None
            
            KAG_CONFIG.initialize(prod=False, config_file=str(config_file))
            
            # 导入项目模块
            import_modules_from_path(".")
            
            # 导入自定义prompt模块（确保prompt被注册）
            try:
                from builder.prompt import (
                    MilitaryDeploymentNERPrompt,
                    MilitaryDeploymentRelationPrompt,
                    MilitaryDeploymentSTDPrompt
                )
            except ImportError:
                pass  # 使用默认Prompt
            
            # 从配置创建抽取器
            builder_config = KAG_CONFIG.all_config.get("kag_builder_pipeline")
            if not builder_config:
                st.error("kag_builder_pipeline配置不存在")
                return None
            
            # 查找extractor配置（支持嵌套结构）
            extractor_config = None
            
            # 检查是否是chain结构
            if isinstance(builder_config, dict) and "chain" in builder_config:
                chain_config = builder_config["chain"]
                if isinstance(chain_config, dict) and "extractor" in chain_config:
                    extractor_config = chain_config["extractor"]
            
            # 如果是列表结构
            elif isinstance(builder_config, list):
                for component in builder_config:
                    if isinstance(component, dict):
                        comp_type = component.get("type", "")
                        if "extractor" in comp_type.lower():
                            extractor_config = component
                            break
            
            # 如果没有找到，创建一个schema_constraint_extractor配置（使用schema）
            if not extractor_config:
                extractor_config = {
                    "type": "schema_constraint_extractor",
                    "llm": KAG_CONFIG.all_config.get("openie_llm", {}),
                    "ner_prompt": {"type": "military_deployment_ner"},  # 使用军事部署专用prompt
                    "relation_prompt": {"type": "military_deployment_relation"},
                    "std_prompt": {"type": "military_deployment_std"},
                }
            else:
                # 如果找到的是knowledge_unit_extractor，替换为schema_constraint_extractor
                extractor_type = extractor_config.get("type", "")
                if "knowledge_unit" in extractor_type.lower() or "schema_free" in extractor_type.lower():
                    # 保留LLM配置，但改用schema_constraint_extractor，并使用军事部署专用prompt
                    extractor_config = {
                        "type": "schema_constraint_extractor",
                        "llm": extractor_config.get("llm", KAG_CONFIG.all_config.get("openie_llm", {})),
                        "ner_prompt": {"type": "military_deployment_ner"},  # 使用军事部署专用prompt
                        "relation_prompt": {"type": "military_deployment_relation"},
                        "std_prompt": {"type": "military_deployment_std"},
                    }
                else:
                    # 如果已经是schema_constraint_extractor，确保使用军事部署专用prompt
                    if extractor_config.get("type") == "schema_constraint_extractor":
                        if "ner_prompt" not in extractor_config or not extractor_config.get("ner_prompt"):
                            extractor_config["ner_prompt"] = {"type": "military_deployment_ner"}
                        if "relation_prompt" not in extractor_config or not extractor_config.get("relation_prompt"):
                            extractor_config["relation_prompt"] = {"type": "military_deployment_relation"}
                        if "std_prompt" not in extractor_config or not extractor_config.get("std_prompt"):
                            extractor_config["std_prompt"] = {"type": "military_deployment_std"}
            
            # 创建抽取器
            extractor = ExtractorABC.from_config(extractor_config)
            
            return extractor
            
        finally:
            os.chdir(original_cwd)
            
    except Exception as e:
        st.error(f"初始化抽取器失败: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None


def extract_knowledge_step_by_step(extractor, text: str, title: str = "输入文本", progress_callback=None):
    """执行知识抽取，返回结果"""
    # 不再构建步骤信息，直接返回空列表
    steps = []
    
    try:
        # 创建Chunk对象
        # 注意：name应该是一个有意义的标题，而不是"用户输入"
        # 如果title是"用户输入"或"输入文本"，使用文本的前50个字符作为标题
        chunk_title = title
        if title in ["用户输入", "输入文本", "输入"]:
            # 使用文本的前50个字符作为标题
            chunk_title = text[:50].replace("\n", " ").strip()
            if len(text) > 50:
                chunk_title += "..."
        
        chunk = Chunk(
            id=str(uuid.uuid4()),
            name=chunk_title,
            content=text,
            type=ChunkTypeEnum.Text
        )
        
        # 直接调用invoke获取完整结果（不再构建步骤信息）
        results = extractor.invoke(chunk)
        subgraph = None
        if results and len(results) > 0:
            result_item = results[0]
            # 处理 BuilderComponentData 包装
            if hasattr(result_item, 'data'):
                subgraph = result_item.data
            else:
                subgraph = result_item
            
            # 确保是 SubGraph 对象
            if not hasattr(subgraph, 'nodes'):
                st.error(f"返回结果类型错误: {type(subgraph)}")
                return None, steps
        
        return subgraph, steps
        
    except Exception as e:
        import traceback
        st.error(traceback.format_exc())
        return None, steps


def _parse_subgraph(value):
    """解析SubGraph数据，支持多种格式"""
    if isinstance(value, SubGraph):
        return value
    elif isinstance(value, list):
        all_nodes = []
        all_edges = []
        for item in value:
            if isinstance(item, SubGraph):
                all_nodes.extend(item.nodes)
                all_edges.extend(item.edges)
            elif hasattr(item, 'data') and isinstance(item.data, SubGraph):
                all_nodes.extend(item.data.nodes)
                all_edges.extend(item.data.edges)
            elif isinstance(item, dict):
                result = _parse_subgraph(item)
                if result:
                    all_nodes.extend(result.nodes)
                    all_edges.extend(result.edges)
        if all_nodes or all_edges:
            return SubGraph(nodes=all_nodes, edges=all_edges)
    elif isinstance(value, dict):
        # 检查是否有resultNodes/resultEdges
        if "resultNodes" in value or "resultEdges" in value:
            nodes = []
            edges = []
            seen_nodes = {}
            
            if "resultNodes" in value:
                for node_data in value["resultNodes"]:
                    node = Node(
                        id=node_data.get("id", node_data.get("name", "")),
                        name=node_data.get("name", node_data.get("id", "")),
                        label=node_data.get("type", node_data.get("label", "")),
                        properties=node_data.get("properties", {})
                    )
                    unique_id = f"{node.id}_{node.label}"
                    if unique_id not in seen_nodes:
                        seen_nodes[unique_id] = node
                        nodes.append(node)
            
            if "resultEdges" in value:
                for edge_data in value["resultEdges"]:
                    from_id = edge_data.get("from", edge_data.get("from_id", ""))
                    to_id = edge_data.get("to", edge_data.get("to_id", ""))
                    from_type = edge_data.get("fromType", edge_data.get("from_type", ""))
                    to_type = edge_data.get("toType", edge_data.get("to_type", ""))
                    
                    from_node = Node(id=from_id, name=from_id, label=from_type, properties={})
                    to_node = Node(id=to_id, name=to_id, label=to_type, properties={})
                    edge = Edge(
                        _id="",
                        from_node=from_node,
                        to_node=to_node,
                        label=edge_data.get("label", ""),
                        properties=edge_data.get("properties", {})
                    )
                    edges.append(edge)
            
            if nodes or edges:
                return SubGraph(nodes=nodes, edges=edges)
    return None


def generate_main_kb_visualization(subgraph: SubGraph, output_path: Path) -> Optional[Path]:
    """
    生成主知识库的可视化文件
    
    Args:
        subgraph: 要可视化的SubGraph对象
        output_path: 输出HTML文件路径（完整路径，包含.html扩展名）
        
    Returns:
        生成的HTML文件路径，如果生成失败返回None
    """
    try:
        # 验证数据
        if not subgraph:
            return None
        
        if not subgraph.nodes and not subgraph.edges:
            return None
        
        from kag.builder.component.reader.enhanced_graph_visualizer import visualize_enhanced_graph
        
        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 生成可视化（传入不带扩展名的路径）
        generated_path = visualize_enhanced_graph(
            subgraph=subgraph,
            source_text="",
            extraction_steps=[],
            output_path=str(output_path.with_suffix(''))
        )
        
        # 返回生成的路径（函数会自动添加.html扩展名）
        result_path = Path(generated_path)
        if result_path.exists() and result_path.stat().st_size > 1000:
            return result_path
        return None
    except Exception as e:
        print(f"[ERROR] 生成可视化失败: {e}")
        import traceback
        traceback.print_exc()
    return None


def create_fixed_manual_graph() -> SubGraph:
    """
    创建固定的"美军作战手册"图谱结构
    
    Returns:
        SubGraph对象，包含中心实体、第一跳实体和第二跳实体
    """
    nodes = []
    edges = []
    
    # 中心实体
    center_node = Node(
        _id="美军作战手册",
        name="美军作战手册",
        label="手册",
        properties={}
    )
    nodes.append(center_node)
    
    # 第一跳实体及其第二跳实体
    first_level_entities = {
        "第一章美军作战思想": [
            "第一节联合军种作战与联军作战",
            "第二节力量投送",
            "第三节非战争军事行动",
            "第四节陆军作战思想与作战原则",
            "第五节海军作战思想与作战原则",
            "第六节空军作战思想与作战原则"
        ],
        "第二章战区战役": [
            "第一节概述",
            "第二节战区战役",
            "第三节海军与海军陆战队的运用",
            "第四节空军的运用"
        ],
        "第三章空中战役": [
            "第一节概述",
            "第二节空中战役的目的、任务和分类",
            "第三节空中战役的兵力编成与区分",
            "第四节空中战役的指挥与协同",
            "第五节空中战役的实施",
            "第六节空中战役的保障"
        ],
        "第四章陆军集团军群作战": [
            "第一节概述",
            "第二节使命与任务",
            "第三节作战计划的制定",
            "第四节作战地带与兵力部署",
            "第五节战役机动方案",
            "第六节火力支援",
            "第七节战役指挥",
            "第八节攻防作战的实施"
        ],
        "第五章陆军军作战": [
            "第一节概述",
            "第二节进攻作战",
            "第三节防御作战"
        ],
        "第六章陆军师战斗": [
            "第一节概述",
            "第二节进攻战斗",
            "第三节防御战斗"
        ],
        "第七章机械化步兵与坦克营攻防战斗": [
            "第一节概述",
            "第二节进攻战斗",
            "第三节防御战斗"
        ],
        "第八章机步排攻防战斗": [
            "第一节概述",
            "第二节进攻战斗",
            "第三节防御战斗"
        ]
    }
    
    # 创建第一跳实体并连接到中心实体
    for first_level_name, second_level_list in first_level_entities.items():
        first_node = Node(
            _id=first_level_name,
            name=first_level_name,
            label="章节",
            properties={}
        )
        nodes.append(first_node)
        
        # 连接到中心实体
        edge = Edge(
            _id=f"{center_node.id}_to_{first_level_name}",
            from_node=center_node,
            to_node=first_node,
            label="包含",
            properties={}
        )
        edges.append(edge)
        
        # 创建第二跳实体并连接到第一跳实体
        for second_level_name in second_level_list:
            # 注意：第二跳可能重名，但不是同一个实体点
            # 用“父章节+分隔符+小节名”生成唯一 ID，避免图上节点合并/多父连接
            second_unique_id = f"{first_level_name}::{second_level_name}"
            second_node = Node(
                _id=second_unique_id,
                name=second_level_name,
                label="小节",
                properties={
                    "chapter": first_level_name,
                    "section": second_level_name,
                }
            )
            nodes.append(second_node)
            
            # 连接到第一跳实体
            edge = Edge(
                _id=f"{first_level_name}_to_{second_unique_id}",
                from_node=first_node,
                to_node=second_node,
                label="包含",
                properties={}
            )
            edges.append(edge)
    
    return SubGraph(nodes=nodes, edges=edges)


def render_graph_visualization(
    subgraph: SubGraph,
    node_color_map: Optional[Dict[str, str]] = None,
    edge_color_map: Optional[Dict[str, str]] = None,
    enable_click_handler: bool = False,
    target_node_id: Optional[str] = None
) -> str:
    """
    通用的图谱可视化函数，用于渲染固定图谱和知识库图谱
    
    Args:
        subgraph: 要可视化的SubGraph对象
        node_color_map: 节点ID到颜色的映射（可选）
        edge_color_map: 关系类型到颜色的映射（可选）
        enable_click_handler: 是否启用点击事件处理（用于固定图谱）
        target_node_id: 目标节点ID（用于触发动画的节点）
        
    Returns:
        生成的HTML内容字符串
    """
    from pyvis.network import Network
    import tempfile
    import os
    
    # 创建网络图
    net = Network(
        height="2400px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="white",
        directed=True
    )
    
    # 默认关系类型配色方案
    default_relation_colors = {
        "位于": "#FF6B9D", "包含": "#4ECDC4", "相邻": "#95E1D3", "连接": "#FECA57",
        "控制": "#48DBFB", "支持": "#FF9FF3", "攻击": "#54A0FF", "防御": "#5F27CD",
        "部署": "#00D2D3", "指挥": "#FF6348", "隶属": "#FFA502", "协同": "#A55EEA",
        "依赖": "#26DE81", "影响": "#FD79A8", "关联": "#FDCB6E", "组成": "#6C5CE7",
        "属于": "#00B894", "执行": "#E17055", "负责": "#74B9FF", "监控": "#A29BFE",
    }
    
    # 使用提供的edge_color_map或默认颜色
    # 收集所有关系类型
    all_relation_types = sorted(set([str(e.label) for e in subgraph.edges if e.label]))
    
    if edge_color_map is None:
        # 如果没有提供edge_color_map，为所有关系类型自动分配颜色
        edge_color_map = {}
        default_colors = [
            "#FF6B9D", "#4ECDC4", "#95E1D3", "#FECA57", "#48DBFB",
            "#FF9FF3", "#54A0FF", "#5F27CD", "#00D2D3", "#FF6348",
            "#FFA502", "#A55EEA", "#26DE81", "#FD79A8", "#FDCB6E",
            "#6C5CE7", "#00B894", "#E17055", "#74B9FF", "#A29BFE",
        ]
        for idx, rel_type in enumerate(all_relation_types):
            edge_color_map[rel_type] = default_relation_colors.get(rel_type, default_colors[idx % len(default_colors)])
    else:
        # 如果提供了edge_color_map，确保所有关系类型都有颜色（补充缺失的关系类型）
        default_colors = [
            "#FF6B9D", "#4ECDC4", "#95E1D3", "#FECA57", "#48DBFB",
            "#FF9FF3", "#54A0FF", "#5F27CD", "#00D2D3", "#FF6348",
            "#FFA502", "#A55EEA", "#26DE81", "#FD79A8", "#FDCB6E",
            "#6C5CE7", "#00B894", "#E17055", "#74B9FF", "#A29BFE",
        ]
        # 为不在edge_color_map中的关系类型分配颜色
        existing_colors = list(edge_color_map.values())
        color_index = 0
        for rel_type in all_relation_types:
            if rel_type not in edge_color_map:
                # 优先使用default_relation_colors中的颜色
                if rel_type in default_relation_colors:
                    edge_color_map[rel_type] = default_relation_colors[rel_type]
                else:
                    # 使用default_colors循环分配
                    edge_color_map[rel_type] = default_colors[color_index % len(default_colors)]
                    color_index += 1
    
    # 统计每个节点参与的关系类型（用于确定节点颜色）
    # 即使提供了node_color_map，也需要统计关系类型，以便为不在map中的节点自动着色
    node_relation_counts = {}
    for edge in subgraph.edges:
        source = str(edge.from_id)
        target = str(edge.to_id)
        relation_type = str(edge.label) if edge.label else "Unknown"
        
        if source not in node_relation_counts:
            node_relation_counts[source] = {}
        if target not in node_relation_counts:
            node_relation_counts[target] = {}
        
        node_relation_counts[source][relation_type] = node_relation_counts[source].get(relation_type, 0) + 1
        node_relation_counts[target][relation_type] = node_relation_counts[target].get(relation_type, 0) + 1
    
    # 添加节点
    entity_map = {}
    for node in subgraph.nodes:
        entity_id = str(node.id)
        entity_name = str(node.name) if node.name else entity_id
        entity_type = str(node.label) if node.label else "Unknown"
        
        # 确定节点颜色
        # 优先级：1. node_color_map中指定的颜色 2. 根据关系类型自动着色 3. 默认灰色
        if node_color_map and entity_id in node_color_map:
            # 如果节点在颜色映射中，使用指定颜色（固定图谱的节点）
            node_color = node_color_map[entity_id]
        elif entity_id in node_relation_counts and node_relation_counts[entity_id]:
            # 如果节点不在颜色映射中，根据其参与的主要关系类型自动着色（主知识库图谱的节点）
            main_relation = max(node_relation_counts[entity_id].items(), key=lambda x: x[1])[0]
            node_color = edge_color_map.get(main_relation, "#888888")
        else:
            # 如果节点没有任何关系，使用默认灰色
            node_color = "#888888"
        
        # 构建节点标题
        title = f"<b>{entity_name}</b><br>类型: {entity_type}<br>ID: {entity_id}"
        if node.properties:
            title += "<br>属性:"
            for key, value in list(node.properties.items())[:5]:
                title += f"<br>  {key}: {value}"
        
        # 添加节点（固定大小25）
        net.add_node(
            entity_id,
            label=entity_name[:20],
            title=title,
            color={
                "background": node_color,
                "border": node_color,
                "highlight": {"background": node_color, "border": "#FFFFFF"},
                "hover": {"background": node_color, "border": "#FFFFFF"}
            },
            font={"color": "#FFFFFF", "size": 14, "face": "Arial"},
            size=25,  # 固定大小
            borderWidth=3,
            borderWidthSelected=5
        )
        entity_map[entity_id] = node
    
    # 添加边
    for edge in subgraph.edges:
        source = str(edge.from_id)
        target = str(edge.to_id)
        relation_type = str(edge.label) if edge.label else "Unknown"
        edge_color = edge_color_map.get(relation_type, "#888888")
        
        if source in entity_map and target in entity_map:
            net.add_edge(
                source,
                target,
                label=relation_type[:15],
                title=relation_type,
                color={"color": edge_color, "highlight": "#FFFFFF", "hover": "#FFFFFF"},
                width=3,
                arrows={"to": {"enabled": True, "scaleFactor": 1.2, "type": "arrow"}},
                font={"color": edge_color, "size": 12, "align": "middle"},
                smooth={"type": "curvedCW", "roundness": 0.2}
            )
    
    # 配置物理引擎
    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -10000,
          "centralGravity": 0.01,
          "springLength": 400,
          "springConstant": 0.02,
          "damping": 0.09
        },
        "stabilization": {
          "enabled": true,
          "iterations": 300,
          "updateInterval": 25,
          "onlyDynamicEdges": false,
          "fit": true
        },
        "adaptiveTimestep": true,
        "maxVelocity": 50
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 200,
        "zoomView": true,
        "dragView": true,
        "dragNodes": true
      }
    }
    """)
    
    # 生成HTML到临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as html_file:
        net.save_graph(html_file.name)
        html_path = html_file.name
    
    # 读取并修改HTML内容
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # 添加稳定后自动禁用物理引擎的代码，并将network实例暴露到window
        if "new vis.Network" in html_content:
            replacement = """var network = new vis.Network(container, data, options);
                    window.__kag_network = network;
                    network.once("stabilizationIterationsDone", function() {
                      network.setOptions({physics: {enabled: false}});
                    });"""
            html_content = html_content.replace("var network = new vis.Network(container, data, options);", replacement, 1)
        
        return html_content
    finally:
        try:
            os.unlink(html_path)
        except:
            pass


def load_main_knowledge_base(ckpt_dir: Path) -> Optional[SubGraph]:
    """
    从主知识库checkpoint加载所有实体和关系，转换为SubGraph
    
    Args:
        ckpt_dir: checkpoint目录路径
        
    Returns:
        SubGraph对象，如果加载失败返回None
    """
    try:
        from diskcache import Cache
        
        all_nodes = []
        all_edges = []
        seen_nodes = {}  # 用于去重: unique_id -> Node
        loaded_count = 0
        
        # 需要检查的组件目录（按优先级排序）
        component_dirs = [
            "KGWriter",  # 最终写入的组件，最重要
            "KAGPostProcessor",  # 后处理器（组件名称保持不变）
            "KnowledgeUnitSchemaFreeExtractor",  # 抽取器
        ]
        
        # 1. 读取各个组件的checkpoint
        for component_name in component_dirs:
            component_dir = ckpt_dir / component_name
            if component_dir.exists():
                try:
                    cache = Cache(str(component_dir))
                    cache_count = 0
                    for key in cache:
                        try:
                            value = cache[key]
                            subgraph = _parse_subgraph(value)
                            if subgraph:
                                cache_count += 1
                                for node in subgraph.nodes:
                                    node_id = node.id
                                    node_label = node.label
                                    unique_id = f"{node_id}_{node_label}"
                                    if unique_id not in seen_nodes:
                                        seen_nodes[unique_id] = node
                                        all_nodes.append(node)
                                for edge in subgraph.edges:
                                    all_edges.append(edge)
                        except Exception as e:
                            continue
                    if cache_count > 0:
                        loaded_count += cache_count
                    cache.close()
                except Exception as e:
                    pass  # 读取checkpoint失败，继续尝试其他组件
        
        # 2. 读取主checkpoint文件
        main_ckpt = ckpt_dir / "kag_checkpoint_0_1.ckpt"
        if main_ckpt.exists():
            try:
                main_count = 0
                with open(main_ckpt, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if "id" in entry and "value" in entry:
                                value = entry["value"]
                                subgraph = _parse_subgraph(value)
                                if subgraph:
                                    main_count += 1
                                    for node in subgraph.nodes:
                                        node_id = node.id
                                        node_label = node.label
                                        unique_id = f"{node_id}_{node_label}"
                                        if unique_id not in seen_nodes:
                                            seen_nodes[unique_id] = node
                                            all_nodes.append(node)
                                    for edge in subgraph.edges:
                                        all_edges.append(edge)
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            continue
                if main_count > 0:
                    loaded_count += main_count
            except Exception as e:
                pass  # 读取主checkpoint文件失败
        
        if not all_nodes and not all_edges:
            return None
        
        # 创建SubGraph
        subgraph = SubGraph(nodes=all_nodes, edges=all_edges)
        # 成功加载主知识库
        return subgraph
        
    except Exception as e:
        st.error(f"加载主知识库失败: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None


async def extract_knowledge_async(extractor, text: str, title: str = "输入文本"):
    """异步执行知识抽取"""
    try:
        chunk = Chunk(
            id=str(uuid.uuid4()),
            name=title,
            content=text,
            type=ChunkTypeEnum.Text
        )
        
        # 使用异步方法
        if hasattr(extractor, 'ainvoke'):
            results = await extractor.ainvoke(chunk)
        else:
            results = extractor.invoke(chunk)
        
        if results and len(results) > 0:
            return results[0]
        return None
        
    except Exception as e:
        st.error(f"抽取失败: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None


def main():
    """主函数"""
    # 使用自定义标题样式
    st.markdown("""
    <div class="fade-in">
        <h1>🧠 知识抽取系统</h1>
        <p style="text-align: center; color: rgba(255, 255, 255, 0.9); font-size: 1.2rem; margin-top: -1rem;">
            <span style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
                🚀 智能知识图谱构建 | 实时抽取监控 | 可视化展示
            </span>
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    
    # 创建标签页
    tab1, tab2 = st.tabs(["📝 知识抽取", "📊 主知识库展示"])
    
    # 初始化会话状态
    if 'main_kb_loaded' not in st.session_state:
        st.session_state.main_kb_loaded = False
    if 'main_kb_subgraph' not in st.session_state:
        st.session_state.main_kb_subgraph = None
    if 'main_kb_selected_entity_types' not in st.session_state:
        st.session_state.main_kb_selected_entity_types = []
    if 'main_kb_selected_relation_types' not in st.session_state:
        st.session_state.main_kb_selected_relation_types = []
    if 'main_kb_search_term' not in st.session_state:
        st.session_state.main_kb_search_term = ""
    if 'show_fixed_graph' not in st.session_state:
        st.session_state.show_fixed_graph = True
    if 'trigger_explosion' not in st.session_state:
        st.session_state.trigger_explosion = False
    if 'show_both_graphs' not in st.session_state:
        st.session_state.show_both_graphs = False
    
    # 自动初始化抽取器（如果尚未初始化）
    if st.session_state.extractor is None:
                st.session_state.extractor = init_extractor()
    
    # 标签页1: 知识抽取
    with tab1:
        input_text = st.text_area(
            "请输入要抽取知识的文本:",
            height=300,
            placeholder="例如：\n2024年，中国人民解放军进行了大规模军事部署。主要部署地点包括北京和上海。\n东部战区作为重要组成部分，参与了此次部署行动。",
            key="input_text",
            help="💡 提示：输入包含实体和关系的文本，系统将自动识别并构建知识图谱"
        )
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            extract_button = st.button("🚀 开始抽取", type="primary", use_container_width=True)
        with col_btn2:
            clear_button = st.button("🗑️ 清空", use_container_width=True)
        
        if clear_button:
            st.session_state.current_result = None
            st.rerun()
    
    # 执行抽取
    if extract_button and input_text.strip():
        if not st.session_state.extractor:
            st.error("❌ 抽取器初始化失败，请检查配置")
        else:
            # 直接执行抽取，不显示过程
            with st.spinner("正在抽取知识..."):
                try:
                    subgraph, steps = extract_knowledge_step_by_step(
                        st.session_state.extractor,
                        input_text,
                        "用户输入"
                    )
                except Exception as e:
                    st.error(f"抽取失败: {e}")
                    subgraph, steps = None, []
            
            # 保存结果
            if subgraph:
                result_data = {
                    "subgraph": subgraph,
                    "source_text": input_text,
                    "steps": steps,
                    "timestamp": time.time()
                }
                st.session_state.current_result = result_data
    
    # 显示结果
    if st.session_state.current_result:
        result = st.session_state.current_result
        subgraph = result.get("subgraph")
        source_text = result.get("source_text", "")
        steps = result.get("steps", [])
        
        if subgraph:
            st.markdown("---")
            st.markdown("""
            <div class="fade-in" style="margin: 2rem 0;">
                <h2 style="color: #ffffff; text-align: center; font-weight: 700; text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);">
                    🎨 知识图谱可视化
                </h2>
                <p style="text-align: center; color: rgba(255, 255, 255, 0.9); margin-top: -0.5rem;">
                    交互式图谱展示 | 实体关系可视化 | 原文高亮对应
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # 使用pyvis创建交互式可视化（与主知识库展示一致）
            if subgraph.nodes or subgraph.edges:
                try:
                    from pyvis.network import Network
                    import tempfile
                    import os
                    
                    # 创建网络图 - 使用深色背景以突出彩色节点
                    net = Network(
                        height="2400px",
                        width="100%",
                        bgcolor="#1a1a2e",  # 深蓝黑色背景
                        font_color="white",
                        directed=True
                    )
                    
                    # 关系类型配色方案
                    relation_type_colors = {
                        "位于": "#FF6B9D", "包含": "#4ECDC4", "相邻": "#95E1D3", "连接": "#FECA57",
                        "控制": "#48DBFB", "支持": "#FF9FF3", "攻击": "#54A0FF", "防御": "#5F27CD",
                        "部署": "#00D2D3", "指挥": "#FF6348", "隶属": "#FFA502", "协同": "#A55EEA",
                        "依赖": "#26DE81", "影响": "#FD79A8", "关联": "#FDCB6E", "组成": "#6C5CE7",
                        "属于": "#00B894", "执行": "#E17055", "负责": "#74B9FF", "监控": "#A29BFE",
                    }
                    
                    # 收集所有关系类型并分配颜色
                    all_relation_types = sorted(set([str(e.label) for e in subgraph.edges if e.label]))
                    relation_color_map = {}
                    default_colors = [
                        "#FF6B9D", "#4ECDC4", "#95E1D3", "#FECA57", "#48DBFB",
                        "#FF9FF3", "#54A0FF", "#5F27CD", "#00D2D3", "#FF6348",
                        "#FFA502", "#A55EEA", "#26DE81", "#FD79A8", "#FDCB6E",
                        "#6C5CE7", "#00B894", "#E17055", "#74B9FF", "#A29BFE",
                    ]
                    
                    for idx, rel_type in enumerate(all_relation_types):
                        if rel_type in relation_type_colors:
                            relation_color_map[rel_type] = relation_type_colors[rel_type]
                        else:
                            relation_color_map[rel_type] = default_colors[idx % len(default_colors)]
                    
                    # 统计每个节点参与的关系类型（用于确定节点颜色）
                    node_relation_counts = {}
                    for edge in subgraph.edges:
                        source = str(edge.from_id)
                        target = str(edge.to_id)
                        relation_type = str(edge.label) if edge.label else "Unknown"
                        
                        if source not in node_relation_counts:
                            node_relation_counts[source] = {}
                        if target not in node_relation_counts:
                            node_relation_counts[target] = {}
                        
                        node_relation_counts[source][relation_type] = node_relation_counts[source].get(relation_type, 0) + 1
                        node_relation_counts[target][relation_type] = node_relation_counts[target].get(relation_type, 0) + 1
                    
                    # 添加节点
                    entity_map = {}
                    for node in subgraph.nodes:
                        entity_id = str(node.id)
                        entity_name = str(node.name) if node.name else entity_id
                        entity_type = str(node.label) if node.label else "Unknown"
                        
                        # 根据节点参与的主要关系类型确定颜色
                        if entity_id in node_relation_counts and node_relation_counts[entity_id]:
                            main_relation = max(node_relation_counts[entity_id].items(), key=lambda x: x[1])[0]
                            node_color = relation_color_map.get(main_relation, "#888888")
                        else:
                            node_color = "#888888"
                        
                        # 构建节点标题
                        title = f"<b>{entity_name}</b><br>类型: {entity_type}<br>ID: {entity_id}"
                        if node.properties:
                            title += "<br>属性:"
                            for key, value in list(node.properties.items())[:5]:
                                title += f"<br>  {key}: {value}"
                        
                        net.add_node(
                            entity_id,
                            label=entity_name[:20],
                            title=title,
                            color={
                                "background": node_color,
                                "border": node_color,
                                "highlight": {"background": node_color, "border": "#FFFFFF"},
                                "hover": {"background": node_color, "border": "#FFFFFF"}
                            },
                            font={"color": "#FFFFFF", "size": 14, "face": "Arial"},
                            size=25,
                            borderWidth=3,
                            borderWidthSelected=5
                        )
                        entity_map[entity_id] = node
                    
                    # 添加边
                    for edge in subgraph.edges:
                        source = str(edge.from_id)
                        target = str(edge.to_id)
                        relation_type = str(edge.label) if edge.label else "Unknown"
                        edge_color = relation_color_map.get(relation_type, "#888888")
                        
                        if source in entity_map and target in entity_map:
                            net.add_edge(
                                source,
                                target,
                                label=relation_type[:15],
                                title=relation_type,
                                color={"color": edge_color, "highlight": "#FFFFFF", "hover": "#FFFFFF"},
                                width=3,
                                arrows={"to": {"enabled": True, "scaleFactor": 1.2, "type": "arrow"}},
                                font={"color": edge_color, "size": 12, "align": "middle"},
                                smooth={"type": "curvedCW", "roundness": 0.2}
                            )
                    
                    # 配置物理引擎
                    net.set_options("""
                    {
                      "physics": {
                        "enabled": true,
                        "barnesHut": {
                          "gravitationalConstant": -10000,
                          "centralGravity": 0.01,
                          "springLength": 400,
                          "springConstant": 0.02,
                          "damping": 0.09
                        },
                        "stabilization": {
                          "enabled": true,
                          "iterations": 300,
                          "updateInterval": 25,
                          "onlyDynamicEdges": false,
                          "fit": true
                        },
                        "adaptiveTimestep": true,
                        "maxVelocity": 50
                      },
                      "interaction": {
                        "hover": true,
                        "tooltipDelay": 200,
                        "zoomView": true,
                        "dragView": true,
                        "dragNodes": true
                      }
                    }
                    """)
                    
                    # 生成HTML到临时文件
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as html_file:
                        net.save_graph(html_file.name)
                        html_path = html_file.name
                    
                    # 读取HTML内容并修改，添加稳定后自动禁用物理引擎的代码
                    try:
                        with open(html_path, "r", encoding="utf-8") as f:
                            html_content = f.read()
                        
                        if "new vis.Network" in html_content:
                            replacement = """var network = new vis.Network(container, data, options);
                    network.once("stabilizationIterationsDone", function() {
                      network.setOptions({physics: {enabled: false}});
                    });"""
                            html_content = html_content.replace("var network = new vis.Network(container, data, options);", replacement, 1)
                        
                        # 在Streamlit中显示
                        st.components.v1.html(html_content, height=2450, scrolling=False)
                    finally:
                        try:
                            os.unlink(html_path)
                        except:
                            pass
                    
                    # 原文高亮功能
                    if source_text:
                        st.markdown("---")
                        st.subheader("📝 原文高亮")
                        
                        # 提取所有实体名称用于高亮
                        entity_names = {}
                        for node in subgraph.nodes:
                            entity_name = str(node.name) if node.name else ""
                            entity_id = str(node.id)
                            if entity_name:
                                entity_names[entity_name] = entity_id
                        
                        # 对原文进行高亮处理
                        highlighted_text = source_text
                        # 按长度从长到短排序，避免短名称覆盖长名称
                        sorted_names = sorted(entity_names.keys(), key=len, reverse=True)
                        for entity_name in sorted_names:
                            if entity_name in highlighted_text:
                                # 使用mark标签高亮实体（使用更亮的颜色，在紫色背景上更清晰）
                                highlighted_text = highlighted_text.replace(
                                    entity_name,
                                    f'<mark style="background-color: #ffd700; color: #1a1a1a; padding: 2px 6px; border-radius: 4px; cursor: pointer; font-weight: 600;" onclick="focusNode(\'{entity_names[entity_name]}\')">{entity_name}</mark>'
                                )
                        
                        # 显示高亮后的文本（背景与网页整体颜色一致）
                        st.markdown(f"""
                        <div style="background: rgba(102, 126, 234, 0.15); 
                                    backdrop-filter: blur(10px);
                                    border-radius: 8px; 
                                    padding: 1.5rem; 
                                    margin: 1rem 0; 
                                    border-left: 4px solid #667eea;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                    color: #f7fafc;
                                    line-height: 1.8;
                                    font-size: 1rem;">
                            {highlighted_text}
                        </div>
                        <script>
                        function focusNode(nodeId) {{
                            // 触发节点聚焦事件（需要与pyvis网络图交互）
                            console.log('Focus node:', nodeId);
                        }}
                        </script>
                        """, unsafe_allow_html=True)
                    
                except ImportError:
                    st.error("pyvis库未安装，请运行: pip install pyvis")
                    st.code("pip install pyvis", language="bash")
                except Exception as e:
                    st.error(f"生成可视化失败: {e}")
                    import traceback
                    st.error(traceback.format_exc())
            else:
                st.info("没有数据可显示")
            
            # 显示原始数据
            with st.expander("📄 查看原始数据（JSON格式）"):
                st.json({
                    "nodes": [
                        {
                            "id": n.id,
                            "name": n.name,
                            "type": n.label,
                            "properties": n.properties
                        }
                        for n in subgraph.nodes
                    ],
                    "edges": [
                        {
                            "from": e.from_id,
                            "to": e.to_id,
                            "label": e.label,
                            "properties": e.properties
                        }
                        for e in subgraph.edges
                    ]
                })
    
    # 标签页2: 主知识库展示
    with tab2:
        # 检查checkpoint目录
        project_path = Path(__file__).parent
        ckpt_dir = project_path / "builder" / "ckpt"
        
        # 初始化状态
        if 'main_kb_subgraph' not in st.session_state:
            st.session_state.main_kb_subgraph = None
        
        # 加载主知识库数据
        if ckpt_dir.exists() and st.session_state.main_kb_subgraph is None:
            subgraph = load_main_knowledge_base(ckpt_dir)
            if subgraph:
                st.session_state.main_kb_subgraph = subgraph
        
        # 根据show_fixed_graph状态决定显示固定图谱还是知识库图谱
        if st.session_state.show_fixed_graph:
            # 显示固定图谱
            # 创建标题
            st.markdown("""
            <div style="position: relative; margin-bottom: 2rem;">
                <div class="fade-in" style="text-align: center;">
                    <h2 style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; text-align: center; margin: 0;">
                        📖 美军作战手册
                    </h2>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 创建固定图谱
            fixed_graph = create_fixed_manual_graph()
            
            # 定义节点颜色映射（中心实体、第一跳、第二跳使用不同颜色）
            node_color_map = {}
            center_color = "#FF6B9D"  # 中心实体颜色
            first_level_color = "#4ECDC4"  # 第一跳实体颜色
            second_level_color = "#FECA57"  # 第二跳实体颜色
            
            # 设置中心实体颜色
            node_color_map["美军作战手册"] = center_color
            
            # 设置第一跳实体颜色
            first_level_names = [
                "第一章美军作战思想", "第二章战区战役", "第三章空中战役",
                "第四章陆军集团军群作战", "第五章陆军军作战", "第六章陆军师战斗",
                "第七章机械化步兵与坦克营攻防战斗", "第八章机步排攻防战斗"
            ]
            for name in first_level_names:
                node_color_map[name] = first_level_color
            
            # 设置第二跳实体颜色
            for node in fixed_graph.nodes:
                if node.id not in node_color_map:
                    node_color_map[node.id] = second_level_color
            
            # 定义边颜色映射
            edge_color_map = {"包含": "#4ECDC4"}
            
            # 使用通用可视化函数渲染固定图谱
            st.markdown("---")
            
            # 添加展开按钮容器（使用CSS绝对定位放在右上角）
            st.markdown("""
            <div style="position: relative; width: 100%;">
                <div id="expand-btn-container" style="position: absolute; top: 10px; right: 10px; z-index: 1000;">
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 展开按钮（放在图谱展示区域右上角）
            if not st.session_state.show_both_graphs:
                col1, col2 = st.columns([10, 1])
                with col2:
                    if st.button("展开", key="expand_compare_btn_top", use_container_width=True):
                        st.session_state.show_both_graphs = True
                        st.rerun()
            
            # 如果展开对比，将两个图谱合并显示在同一个区域
            if st.session_state.show_both_graphs:
                st.markdown("""
                <div class="fade-in" style="margin: 2rem 0;">
                    <h2 style="color: #ffffff; text-align: center; font-weight: 700; text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);">
                        🎨 图谱对比展示（固定图谱 + 主知识库）
                    </h2>
                </div>
                """, unsafe_allow_html=True)
                
                # 合并固定图谱和主知识库图谱
                kb_subgraph = st.session_state.main_kb_subgraph
                if kb_subgraph and (kb_subgraph.nodes or kb_subgraph.edges):
                    # 合并节点和边
                    merged_nodes = list(fixed_graph.nodes) + list(kb_subgraph.nodes)
                    merged_edges = list(fixed_graph.edges) + list(kb_subgraph.edges)
                    
                    # 找到固定图谱中的"第七章机械化步兵与坦克营攻防战斗::第三节防御战斗"节点
                    fixed_defense_node = None
                    for node in fixed_graph.nodes:
                        if node.id == "第七章机械化步兵与坦克营攻防战斗::第三节防御战斗":
                            fixed_defense_node = node
                            break
                    
                    # 找到主知识库中的名称为“1”的节点，与固定图谱的小节建立关联
                    kb_target_node = None
                    for node in kb_subgraph.nodes:
                        try:
                            node_name = str(node.name).strip() if node.name is not None else ""
                        except Exception:
                            node_name = ""
                        if node_name == "1":
                            kb_target_node = node
                            break
                    
                    # 如果找到了两个节点，创建连接边
                    if fixed_defense_node and kb_target_node:
                        connection_edge = Edge(
                            _id=f"fixed_defense_to_kb_node1_{fixed_defense_node.id}_{kb_target_node.id}",
                            from_node=fixed_defense_node,
                            to_node=kb_target_node,
                            label="关联",
                            properties={}
                        )
                        merged_edges.append(connection_edge)
                    
                    # 创建合并后的SubGraph
                    merged_graph = SubGraph(nodes=merged_nodes, edges=merged_edges)
                    
                    # 合并节点颜色映射（固定图谱使用自定义颜色，知识库图谱根据关系类型自动着色）
                    merged_node_color_map = node_color_map.copy()  # 先复制固定图谱的颜色映射
                    # 知识库图谱的节点颜色会在render_graph_visualization中根据关系类型自动确定
                    
                    # 合并边颜色映射：传入None让render_graph_visualization自动为所有关系类型分配颜色
                    # 这样主知识库图谱的关系类型也能获得正确的颜色
                    merged_edge_color_map = None  # 传入None，让函数自动处理所有关系类型
                    
                    try:
                        merged_html = render_graph_visualization(
                            subgraph=merged_graph,
                            node_color_map=merged_node_color_map,  # 固定图谱节点使用指定颜色，其他节点根据关系类型自动着色
                            edge_color_map=merged_edge_color_map,  # None表示自动为所有关系类型分配颜色
                            enable_click_handler=False,
                            target_node_id=None
                        )
                        st.components.v1.html(merged_html, height=2450, scrolling=False)
                    except Exception as e:
                        st.error(f"生成合并图谱可视化失败: {e}")
                        import traceback
                        st.error(traceback.format_exc())
                else:
                    st.warning("⚠️ 未找到主知识库数据，只显示固定图谱")
                    try:
                        fixed_html = render_graph_visualization(
                            subgraph=fixed_graph,
                            node_color_map=node_color_map,
                            edge_color_map=edge_color_map,
                            enable_click_handler=False,
                            target_node_id=None
                        )
                        st.components.v1.html(fixed_html, height=2450, scrolling=False)
                    except Exception as e:
                        st.error(f"生成固定图谱可视化失败: {e}")
                
                # 添加关闭按钮
                col1, col2 = st.columns([10, 1])
                with col2:
                    if st.button("关闭", key="close_compare_btn", use_container_width=True):
                        st.session_state.show_both_graphs = False
                        st.rerun()
            else:
                # 只显示固定图谱
                # 创建图谱展示区域容器，包含标题和右上角按钮
                st.markdown("""
                <div style="position: relative; margin: 2rem 0;">
                    <div class="fade-in" style="text-align: center;">
                        <h2 style="color: #ffffff; text-align: center; font-weight: 700; text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);">
                            🎨 知识图谱可视化
                        </h2>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 展开按钮（放在图谱上方，右对齐）
                col1, col2 = st.columns([10, 1])
                with col2:
                    if st.button("展开", key="expand_compare_btn_single", use_container_width=True):
                        st.session_state.show_both_graphs = True
                        st.rerun()
                
                try:
                    html_content = render_graph_visualization(
                        subgraph=fixed_graph,
                        node_color_map=node_color_map,
                        edge_color_map=edge_color_map,
                        enable_click_handler=False,
                        target_node_id=None
                    )

                    # 显示固定图谱
                    st.components.v1.html(html_content, height=2450, scrolling=False)
                except Exception as e:
                    st.error(f"生成固定图谱可视化失败: {e}")
                    import traceback
                    st.error(traceback.format_exc())

            # 关键：在展示固定图谱时，不再继续渲染下面的主知识库内容
            # 只有当点击目标节点触发 switchToKB 并 rerun 后，才会进入 else 分支展示主知识库图谱
            st.stop()
        else:
            # 显示知识库图谱
            st.markdown("""
            <div class="fade-in">
                <h2 style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; text-align: center;">
                    📊 主知识库展示
                </h2>
                <p style="text-align: center; color: #666; margin-top: -0.5rem;">
                    浏览主知识库 | 可视化展示所有实体和关系
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # 刷新按钮
            if st.button("🔄 刷新主知识库", type="primary", use_container_width=True, key="refresh_main_kb"):
                if ckpt_dir.exists():
                    subgraph = load_main_knowledge_base(ckpt_dir)
                    if subgraph:
                        st.session_state.main_kb_subgraph = subgraph
                # 清除可视化缓存，强制重新生成
                cache_file = Path(__file__).parent / "visualizations" / "main_kb_visualization.html"
                if cache_file.exists():
                    cache_file.unlink()
            
            # 显示主知识库数据
            subgraph = st.session_state.main_kb_subgraph
        
        if subgraph is None:
            st.info("💡 未找到主知识库数据，请确保已构建知识库。")
        elif not subgraph.nodes and not subgraph.edges:
            st.warning("⚠️ 主知识库为空，没有实体和关系数据。")
        else:
            # 统计信息
            st.markdown("---")
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            with col_stat1:
                st.metric("🎯 实体总数", len(subgraph.nodes), delta=None)
            with col_stat2:
                st.metric("🔗 关系总数", len(subgraph.edges), delta=None)
            with col_stat3:
                entity_types = len(set(n.label for n in subgraph.nodes)) if subgraph.nodes else 0
                st.metric("📋 实体类型", entity_types, delta=None)
            with col_stat4:
                relation_types = len(set(e.label for e in subgraph.edges)) if subgraph.edges else 0
                st.metric("🔖 关系类型", relation_types, delta=None)
            
            # 筛选和搜索控件
            st.markdown("---")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                search_term = st.text_input(
                    "🔍 搜索实体",
                    value=st.session_state.main_kb_search_term,
                    placeholder="输入实体名称进行搜索...",
                    key="main_kb_search_input"
                )
                if search_term != st.session_state.main_kb_search_term:
                    st.session_state.main_kb_search_term = search_term
                    st.rerun()
            
            with col2:
                if st.button("🔄 重置筛选", key="reset_main_kb_filters"):
                    st.session_state.main_kb_selected_entity_types = []
                    st.session_state.main_kb_selected_relation_types = []
                    st.session_state.main_kb_search_term = ""
                    st.rerun()
            
            # 筛选控件
            col1, col2 = st.columns(2)
            with col1:
                # 实体类型筛选
                all_entity_types = sorted(set([str(n.label) for n in subgraph.nodes if n.label]))
                selected_entity_types = st.multiselect(
                    "筛选实体类型",
                    options=all_entity_types,
                    default=st.session_state.main_kb_selected_entity_types,
                    key="main_kb_entity_type_filter"
                )
                if selected_entity_types != st.session_state.main_kb_selected_entity_types:
                    st.session_state.main_kb_selected_entity_types = selected_entity_types
                    st.rerun()
            
            with col2:
                # 关系类型筛选
                all_relation_types = sorted(set([str(e.label) for e in subgraph.edges if e.label]))
                selected_relation_types = st.multiselect(
                    "筛选关系类型",
                    options=all_relation_types,
                    default=st.session_state.main_kb_selected_relation_types,
                    key="main_kb_relation_type_filter"
                )
                if selected_relation_types != st.session_state.main_kb_selected_relation_types:
                    st.session_state.main_kb_selected_relation_types = selected_relation_types
                    st.rerun()
            
            # 应用筛选和搜索
            filtered_nodes = list(subgraph.nodes)
            filtered_edges = list(subgraph.edges)
            
            # 实体类型筛选
            if st.session_state.main_kb_selected_entity_types:
                filtered_nodes = [
                    n for n in filtered_nodes
                    if str(n.label) in st.session_state.main_kb_selected_entity_types
                ]
                # 只显示与筛选实体相关的边
                filtered_node_ids = set([str(n.id) for n in filtered_nodes])
                filtered_edges = [
                    e for e in filtered_edges
                    if str(e.from_id) in filtered_node_ids and str(e.to_id) in filtered_node_ids
                ]
            
            # 关系类型筛选
            if st.session_state.main_kb_selected_relation_types:
                filtered_edges = [
                    e for e in filtered_edges
                    if str(e.label) in st.session_state.main_kb_selected_relation_types
                ]
                # 只显示与筛选关系相关的实体
                related_node_ids = set()
                for e in filtered_edges:
                    related_node_ids.add(str(e.from_id))
                    related_node_ids.add(str(e.to_id))
                filtered_nodes = [
                    n for n in filtered_nodes
                    if str(n.id) in related_node_ids
                ]
            
            # 搜索筛选
            if st.session_state.main_kb_search_term:
                search_lower = st.session_state.main_kb_search_term.lower()
                filtered_nodes = [
                    n for n in filtered_nodes
                    if search_lower in str(n.name).lower() or search_lower in str(n.id).lower()
                ]
                filtered_node_ids = set([str(n.id) for n in filtered_nodes])
                filtered_edges = [
                    e for e in filtered_edges
                    if str(e.from_id) in filtered_node_ids and str(e.to_id) in filtered_node_ids
                ]
            
            st.write(f"**显示**: {len(filtered_nodes)} 个实体, {len(filtered_edges)} 个关系")
            
            # 可视化
            st.markdown("---")
            st.markdown("""
            <div class="fade-in" style="margin: 2rem 0;">
                <h2 style="color: #ffffff; text-align: center; font-weight: 700; text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);">
                    🎨 知识图谱可视化
                </h2>
            </div>
            """, unsafe_allow_html=True)
            
            # 使用通用可视化函数渲染知识库图谱（使用筛选后的数据）
            if filtered_nodes or filtered_edges:
                try:
                    # 创建筛选后的SubGraph
                    filtered_subgraph = SubGraph(nodes=filtered_nodes, edges=filtered_edges)
                    
                    # 使用通用可视化函数
                    html_content = render_graph_visualization(
                        subgraph=filtered_subgraph,
                        node_color_map=None,  # 使用默认颜色映射（基于关系类型）
                        edge_color_map=None,  # 使用默认颜色映射
                        enable_click_handler=False,  # 知识库图谱不需要点击处理
                        target_node_id=None
                    )
                    st.components.v1.html(html_content, height=2450, scrolling=False)
                except Exception as e:
                    st.error(f"生成知识库图谱可视化失败: {e}")
                    import traceback
                    st.error(traceback.format_exc())
                    
                    # 原文对照部分 - 使用分段卡片展示（在try块内，finally块之后）
                    st.markdown("---")
                    st.subheader("📝 节点原文")
                    
                    # 提取原文信息
                    def extract_source_text(node_or_edge):
                        """从节点或关系中提取原文信息"""
                        source_texts = []
                        properties = node_or_edge.properties if hasattr(node_or_edge, 'properties') else {}
                        
                        # 常见的原文字段
                        text_fields = ["desc", "description", "content", "text", "ruleContent", "ruleName", "source_text"]
                        
                        for field in text_fields:
                            if field in properties:
                                value = properties[field]
                                if value and isinstance(value, str) and value.strip():
                                    source_texts.append(value)
                        
                        # 如果没有找到常见的原文字段，尝试显示所有文本类型的属性
                        if not source_texts:
                            for key, value in properties.items():
                                if isinstance(value, str) and len(value) > 10:  # 只显示较长的文本
                                    source_texts.append(value)
                        
                        return source_texts
                    
                    # 收集所有节点的原文（使用筛选后的节点）
                    node_texts = []
                    for node in filtered_nodes:
                        entity_name = str(node.name) if node.name else str(node.id)
                        entity_type = str(node.label) if node.label else "Unknown"
                        source_texts = extract_source_text(node)
                        
                        for text in source_texts:
                            node_texts.append({
                                "entity_name": entity_name,
                                "entity_type": entity_type,
                                "text": text
                            })
                    
                    # 分页显示（类似图片中的样式）
                    if node_texts:
                        # 每页显示数量
                        items_per_page = 5
                        total_pages = (len(node_texts) + items_per_page - 1) // items_per_page
                        
                        if 'main_kb_text_page' not in st.session_state:
                            st.session_state.main_kb_text_page = 1
                        
                        # 获取当前页的数据
                        page = st.session_state.main_kb_text_page
                        start_idx = (page - 1) * items_per_page
                        end_idx = min(start_idx + items_per_page, len(node_texts))
                        current_page_texts = node_texts[start_idx:end_idx]
                        
                        # 显示当前页的分段（使用卡片样式）
                        for idx, text_item in enumerate(current_page_texts, start=start_idx + 1):
                            # 使用markdown创建卡片样式（背景与网页色调一致，文字为深色）
                            st.markdown(f"""
                            <div style="background: rgba(102, 126, 234, 0.15); 
                                        backdrop-filter: blur(10px);
                                        border-radius: 8px; 
                                        padding: 1rem; 
                                        margin: 0.5rem 0; 
                                        border-left: 4px solid #667eea;
                                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <div style="font-size: 0.85rem; color: #f7fafc; margin-bottom: 0.5rem; font-weight: 600;">
                                    <strong>{text_item['entity_name']}</strong> ({text_item['entity_type']})
                                </div>
                                <div style="color: #f7fafc; line-height: 1.6;">
                                    {text_item['text']}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        # 分页控件
                        if total_pages > 1:
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                page_cols = st.columns(min(7, total_pages + 2))  # 最多显示7个按钮
                            
                            # 上一页按钮
                            if page > 1:
                                with page_cols[0]:
                                    if st.button("←", key="prev_page_text"):
                                        st.session_state.main_kb_text_page = page - 1
                                        st.rerun()
                            
                            # 页码按钮（最多显示5页）
                            max_display_pages = 5
                            if total_pages <= max_display_pages:
                                display_pages = list(range(1, total_pages + 1))
                            else:
                                if page <= 3:
                                    display_pages = list(range(1, max_display_pages + 1))
                                elif page >= total_pages - 2:
                                    display_pages = list(range(total_pages - max_display_pages + 1, total_pages + 1))
                                else:
                                    display_pages = list(range(page - 2, page + 3))
                            
                            for i, p in enumerate(display_pages):
                                col_idx = (i + 1) if page > 1 else i
                                if col_idx < len(page_cols):
                                    with page_cols[col_idx]:
                                        if st.button(str(p), key=f"page_{p}_text", disabled=(p == page)):
                                            if p != page:
                                                st.session_state.main_kb_text_page = p
                                                st.rerun()
                            
                            # 下一页按钮
                            if page < total_pages:
                                next_col_idx = len(display_pages) + (1 if page > 1 else 0)
                                if next_col_idx < len(page_cols):
                                    with page_cols[next_col_idx]:
                                        if st.button("→", key="next_page_text"):
                                            st.session_state.main_kb_text_page = page + 1
                                            st.rerun()
                        
                        # 提示信息
                        st.caption(f"最多展示{max_display_pages}页分段，若内容过多，可能无法展示所有分段")
                    else:
                        st.info("暂无节点原文内容")
                        
                except ImportError:
                    st.error("pyvis库未安装，请运行: pip install pyvis")
                    st.code("pip install pyvis", language="bash")
                except Exception as e:
                    st.error(f"生成可视化失败: {e}")
                    import traceback
                    st.code(traceback.format_exc())
            else:
                st.info("没有数据可显示。请调整筛选条件。")
            
            # 显示原始数据
            with st.expander("📄 查看原始数据（JSON格式）"):
                st.json({
                    "nodes": [
                        {
                            "id": n.id,
                            "name": n.name,
                            "type": n.label,
                            "properties": n.properties
                        }
                        for n in subgraph.nodes
                    ],
                    "edges": [
                        {
                            "from": e.from_id,
                            "to": e.to_id,
                            "label": e.label,
                            "properties": e.properties
                        }
                        for e in subgraph.edges
                    ]
                })


if __name__ == "__main__":
    main()

