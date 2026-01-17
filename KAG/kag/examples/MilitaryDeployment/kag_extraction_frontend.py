# -*- coding: utf-8 -*-
"""
知识抽取交互式前端
支持输入文本并实时进行知识抽取，展示抽取过程和结果

使用方法:
    方式1: python -m streamlit run kag_extraction_frontend.py --server.port 9501 --server.address=0.0.0.0
    方式2: streamlit run kag_extraction_frontend.py --server.port 9501 --server.address=0.0.0.0 (如果streamlit在PATH中)
    
    注意: 默认端口已配置为9501（避免与外层系统的8501冲突），已配置允许局域网访问
    
或者使用启动脚本（推荐）:
    Windows: 双击运行 run_extraction_frontend.bat
    Linux/Mac: ./run_extraction_frontend.sh
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
    print("  方式1: python -m streamlit run kag_extraction_frontend.py --server.port 9501 --server.address=0.0.0.0")
    print("  方式2: streamlit run kag_extraction_frontend.py --server.port 9501 --server.address=0.0.0.0 (如果streamlit在PATH中)")
    print("\n  注意: 默认端口已配置为9501（避免与外层系统的8501冲突），已配置允许局域网访问")
    print("\n或者使用启动脚本（推荐）:")
    print("  Windows: 双击运行 run_extraction_frontend.bat")
    print("  Linux/Mac: ./run_extraction_frontend.sh")
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
    """逐步执行知识抽取，返回每个步骤的结果"""
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
        
        passage = f"{chunk_title}\n{text}"
        
        # 步骤1: 实体识别
        step1 = {
            "step": 1,
            "name": "实体识别 (NER)",
            "status": "running",
            "description": "正在识别文本中的实体...",
            "entities": [],
            "timestamp": time.time()
        }
        steps.append(step1)
        if progress_callback:
            progress_callback(1, 4, "步骤 1/4: 实体识别...")
        
        # 执行实体识别
        entities = []
        if hasattr(extractor, 'named_entity_recognition'):
            try:
                if progress_callback:
                    progress_callback(1, 4, "步骤 1/4: 正在进行实体识别...")
                entities = extractor.named_entity_recognition(passage)
                # 确保entities是列表
                if entities is None:
                    entities = []
                elif not isinstance(entities, list):
                    if progress_callback:
                        progress_callback(1, 4, f"⚠️ 实体识别返回了非列表类型: {type(entities)}，正在转换...")
                    entities = [entities] if entities else []
                else:
                    if progress_callback:
                        progress_callback(1, 4, f"✅ 实体识别完成，识别出 {len(entities)} 个实体")
            except Exception as e:
                if progress_callback:
                    progress_callback(1, 4, f"❌ 实体识别失败: {str(e)}，改用完整抽取流程")
                entities = []
        
        # 如果没有获取到实体，使用完整抽取流程
        if not entities:
            if progress_callback:
                progress_callback(1, 4, "🔄 使用完整抽取流程（invoke方法）...")
            # 直接调用invoke获取完整结果
            results = extractor.invoke(chunk)
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
                
                entities = [{"name": n.name, "category": n.label} for n in subgraph.nodes]
                # 如果已经获取到完整结果，直接返回
                steps[-1]["status"] = "completed"
                steps[-1]["description"] = f"识别出 {len(entities)} 个实体"
                steps[-1]["entities"] = [
                    {"name": e.get("name", ""), "type": e.get("category", "")}
                    for e in entities[:20]
                ]
                
                # 添加关系信息
                steps.append({
                    "step": 2,
                    "name": "关系抽取",
                    "status": "completed",
                    "description": f"抽取了 {len(subgraph.edges)} 条关系",
                    "relations": [
                        {
                            "from": e.from_id,
                            "to": e.to_id,
                            "label": e.label
                        }
                        for e in subgraph.edges[:20]
                    ],
                    "timestamp": time.time()
                })
                
                # 添加图谱构建信息
                steps.append({
                    "step": 3,
                    "name": "图谱构建",
                    "status": "completed",
                    "description": f"构建包含 {len(subgraph.nodes)} 个节点和 {len(subgraph.edges)} 条边的知识图谱",
                    "timestamp": time.time()
                })
                
                if progress_callback:
                    progress_callback(3, 3, "✅ 抽取完成！")
                
                return subgraph, steps
        
        step1["status"] = "completed"
        step1["description"] = f"识别出 {len(entities)} 个实体"
        step1["entities"] = [
            {"name": e.get("name", ""), "type": e.get("category", "")}
            for e in entities[:20]
        ]
        
        # 步骤2: 实体标准化
        step2 = {
            "step": 2,
            "name": "实体标准化",
            "status": "running",
            "description": "正在标准化实体名称...",
            "timestamp": time.time()
        }
        steps.append(step2)
        if progress_callback:
            progress_callback(2, 4, "步骤 2/4: 实体标准化...")
        
        # 执行实体标准化
        std_entities = []
        named_entities = [{"name": e.get("name", ""), "category": e.get("category", "")} for e in entities]
        if hasattr(extractor, 'named_entity_standardization'):
            try:
                if progress_callback:
                    progress_callback(2, 4, f"步骤 2/4: 正在标准化 {len(named_entities)} 个实体...")
                std_entities = extractor.named_entity_standardization(passage, named_entities)
                if progress_callback:
                    progress_callback(2, 4, f"✅ 实体标准化完成，标准化了 {len(std_entities) if std_entities else len(entities)} 个实体")
            except Exception as e:
                if progress_callback:
                    progress_callback(2, 4, f"⚠️ 实体标准化失败: {str(e)}")
        elif hasattr(extractor, '_named_entity_standardization_llm'):
            try:
                if progress_callback:
                    progress_callback(2, 4, f"步骤 2/4: 正在标准化 {len(named_entities)} 个实体...")
                std_entities = extractor._named_entity_standardization_llm(passage, named_entities)
                if progress_callback:
                    progress_callback(2, 4, f"✅ 实体标准化完成")
            except Exception as e:
                if progress_callback:
                    progress_callback(2, 4, f"⚠️ 实体标准化失败: {str(e)}")
        
        step2["status"] = "completed"
        step2["description"] = f"标准化了 {len(std_entities) if std_entities else len(entities)} 个实体"
        
        # 步骤3: 关系抽取
        step3 = {
            "step": 3,
            "name": "关系抽取",
            "status": "running",
            "description": "正在抽取实体间的关系...",
            "timestamp": time.time()
        }
        steps.append(step3)
        if progress_callback:
            progress_callback(3, 4, "步骤 3/4: 关系抽取...")
        
        # 执行关系抽取
        relations = []
        if hasattr(extractor, 'relations_extraction'):
            try:
                if progress_callback:
                    progress_callback(3, 4, f"步骤 3/4: 正在抽取实体间的关系（基于 {len(named_entities)} 个实体）...")
                relations = extractor.relations_extraction(passage, named_entities)
                if progress_callback:
                    progress_callback(3, 4, f"✅ 关系抽取完成，抽取了 {len(relations)} 条关系")
            except Exception as e:
                if progress_callback:
                    progress_callback(3, 4, f"⚠️ 关系抽取失败: {str(e)}")
        elif hasattr(extractor, '_relations_extraction_llm'):
            try:
                if progress_callback:
                    progress_callback(3, 4, f"步骤 3/4: 正在抽取实体间的关系...")
                relations = extractor._relations_extraction_llm(passage, named_entities)
                if progress_callback:
                    progress_callback(3, 4, f"✅ 关系抽取完成，抽取了 {len(relations)} 条关系")
            except Exception as e:
                if progress_callback:
                    progress_callback(3, 4, f"⚠️ 关系抽取失败: {str(e)}")
        
        step3["status"] = "completed"
        step3["description"] = f"抽取了 {len(relations)} 条关系"
        if relations:
            step3["relations"] = [
                {
                    "from": rel.get("subject", rel.get("from", "")),
                    "to": rel.get("object", rel.get("to", "")),
                    "label": rel.get("predicate", rel.get("label", ""))
                }
                for rel in relations[:20]
            ]
        
        # 步骤4: 图谱构建
        step4 = {
            "step": 4,
            "name": "图谱构建",
            "status": "running",
            "description": "正在构建知识图谱...",
            "timestamp": time.time()
        }
        steps.append(step4)
        if progress_callback:
            progress_callback(4, 4, "步骤 4/4: 图谱构建...")
        
        # 执行完整抽取以获取SubGraph
        if progress_callback:
            progress_callback(4, 4, "步骤 4/4: 正在构建知识图谱...")
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
                subgraph = None
        
        step4["status"] = "completed"
        if subgraph:
            step4["description"] = f"构建包含 {len(subgraph.nodes)} 个节点和 {len(subgraph.edges)} 条边的知识图谱"
        else:
            step4["description"] = "图谱构建完成"
        
        if progress_callback:
            progress_callback(4, 4, "✅ 抽取完成！")
        
        return subgraph, steps
        
    except Exception as e:
        if steps:
            steps[-1]["status"] = "error"
            steps[-1]["description"] = f"抽取失败: {str(e)}"
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
                <h2 style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; text-align: center;">
                    🎨 知识图谱可视化
                </h2>
                <p style="text-align: center; color: rgba(255, 255, 255, 0.9); margin-top: -0.5rem;">
                    交互式图谱展示 | 实体关系可视化 | 原文高亮对应
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # 生成可视化（可视化文件保存到visualizations目录，不影响主知识库）
            output_dir = Path(__file__).parent / "visualizations"
            output_dir.mkdir(exist_ok=True)
            
            output_file = output_dir / f"extraction_{int(time.time())}.html"
            
            try:
                with st.spinner("🎨 正在生成可视化..."):
                    visualize_enhanced_graph(
                        subgraph=subgraph,
                        source_text=source_text,
                        extraction_steps=steps,
                        output_path=str(output_file.with_suffix(''))
                    )
                
                # 显示HTML文件（直接嵌入页面，不使用iframe滚动）
                with open(output_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # 直接显示HTML内容，不使用iframe的滚动条
                st.components.v1.html(html_content, height=800, scrolling=False)
                
                # 下载按钮（使用更酷炫的样式）
                col_dl1, col_dl2, col_dl3 = st.columns([1, 2, 1])
                with col_dl2:
                    with open(output_file, 'rb') as f:
                        st.download_button(
                            label="📥 下载可视化结果 (HTML)",
                            data=f.read(),
                            file_name=output_file.name,
                            mime="text/html",
                            use_container_width=True,
                            type="primary"
                        )
                
            except Exception as e:
                st.error(f"生成可视化失败: {e}")
                import traceback
                st.error(traceback.format_exc())
            
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
                <h2 style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; text-align: center;">
                    🎨 知识图谱可视化
                </h2>
            </div>
            """, unsafe_allow_html=True)
            
            # 使用pyvis创建交互式可视化（使用筛选后的数据）
            if filtered_nodes or filtered_edges:
                try:
                    from pyvis.network import Network
                    import tempfile
                    import os
                    
                    # 创建网络图
                    net = Network(
                        height="600px",
                        width="100%",
                        bgcolor="#222222",
                        font_color="white",
                        directed=True
                    )
                    
                    # 实体类型颜色映射
                    entity_type_colors = {
                        "MilitaryUnit": "#FF6B6B",
                        "TerrainFeature": "#4ECDC4",
                        "Weapon": "#FFE66D",
                        "Obstacle": "#95E1D3",
                        "DefensePosition": "#F38181",
                        "CombatPosition": "#AA96DA",
                        "UnitOrganization": "#FCBAD3",
                        "CombatTask": "#A8E6CF",
                        "FireSupport": "#FFD3A5",
                        "ObservationPost": "#FD9853",
                        "KillZone": "#A8DADC",
                        "ObstacleBelt": "#457B9D",
                        "SupportPoint": "#E63946",
                        "ApproachRoute": "#F1FAEE"
                    }
                    
                    # 添加节点（使用筛选后的节点）
                    entity_map = {}
                    for node in filtered_nodes:
                        entity_id = str(node.id)
                        entity_name = str(node.name) if node.name else entity_id
                        entity_type = str(node.label) if node.label else "Unknown"
                        color = entity_type_colors.get(entity_type, "#888888")
                        
                        # 构建节点标题（显示详细信息）
                        title = f"<b>{entity_name}</b><br>类型: {entity_type}<br>ID: {entity_id}"
                        if node.properties:
                            title += "<br>属性:"
                            for key, value in list(node.properties.items())[:5]:  # 只显示前5个属性
                                title += f"<br>  {key}: {value}"
                        
                        net.add_node(
                            entity_id,
                            label=entity_name[:20],  # 限制标签长度
                            title=title,
                            color=color,
                            size=20
                        )
                        entity_map[entity_id] = node
                    
                    # 添加边（使用筛选后的边）
                    for edge in filtered_edges:
                        source = str(edge.from_id)
                        target = str(edge.to_id)
                        relation_type = str(edge.label) if edge.label else "Unknown"
                        
                        if source in entity_map and target in entity_map:
                            net.add_edge(
                                source,
                                target,
                                label=relation_type[:15],  # 限制标签长度
                                title=relation_type,
                                color="#888888",
                                width=2
                            )
                    
                    # 配置物理引擎 - 先稳定布局，然后禁用让图保持静止
                    net.set_options("""
                    {
                      "physics": {
                        "enabled": true,
                        "barnesHut": {
                          "gravitationalConstant": -2000,
                          "centralGravity": 0.1,
                          "springLength": 200,
                          "springConstant": 0.04,
                          "damping": 0.09
                        },
                        "stabilization": {
                          "enabled": true,
                          "iterations": 200,
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
                        
                        # 在network初始化后添加监听器，稳定后自动禁用物理引擎
                        # 查找network初始化代码的位置
                        if "new vis.Network" in html_content:
                            # 在network创建后添加事件监听器
                            replacement = """var network = new vis.Network(container, data, options);
                    network.once("stabilizationIterationsDone", function() {
                      network.setOptions({physics: {enabled: false}});
                    });"""
                            html_content = html_content.replace("var network = new vis.Network(container, data, options);", replacement, 1)
                        
                        # 在Streamlit中显示
                        st.components.v1.html(html_content, height=650, scrolling=False)
                    finally:
                        # 清理临时文件
                        try:
                            os.unlink(html_path)
                        except:
                            pass
                    
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
                            # 使用markdown创建卡片样式
                            st.markdown(f"""
                            <div style="background: rgba(255, 255, 255, 0.95); 
                                        border-radius: 8px; 
                                        padding: 1rem; 
                                        margin: 0.5rem 0; 
                                        border-left: 4px solid #667eea;
                                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <div style="font-size: 0.85rem; color: #666; margin-bottom: 0.5rem;">
                                    <strong>{text_item['entity_name']}</strong> ({text_item['entity_type']})
                                </div>
                                <div style="color: #333; line-height: 1.6;">
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

