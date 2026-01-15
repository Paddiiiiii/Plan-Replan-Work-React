# -*- coding: utf-8 -*-
"""
KAG 知识抽取交互式前端
支持输入文本并实时进行知识抽取，展示抽取过程和结果

使用方法:
    方式1: python -m streamlit run kag_extraction_frontend.py
    方式2: streamlit run kag_extraction_frontend.py (如果streamlit在PATH中)
    
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

# 检查是否使用streamlit run启动
if __name__ == "__main__" and "streamlit" not in sys.modules:
    print("=" * 60)
    print("错误: 请使用 streamlit 命令启动此应用")
    print("=" * 60)
    print("\n正确的启动方式:")
    print("  方式1: python -m streamlit run kag_extraction_frontend.py")
    print("  方式2: streamlit run kag_extraction_frontend.py (如果streamlit在PATH中)")
    print("\n或者使用启动脚本（推荐）:")
    print("  Windows: 双击运行 run_extraction_frontend.bat")
    print("  Linux/Mac: ./run_extraction_frontend.sh")
    print("=" * 60)
    sys.exit(1)

import streamlit as st

# 添加KAG根目录到路径
KAG_ROOT = Path(__file__).resolve().parents[3]
if str(KAG_ROOT) not in sys.path:
    sys.path.insert(0, str(KAG_ROOT))

# 设置页面配置
st.set_page_config(
    page_title="KAG 知识抽取系统",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 注入自定义CSS样式
st.markdown("""
<style>
    /* 全局样式 */
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
    }
    
    /* 标题样式 */
    h1 {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
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
        background: rgba(255, 255, 255, 0.95) !important;
        border-radius: 20px !important;
        padding: 1.5rem !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        backdrop-filter: blur(10px) !important;
        transition: transform 0.3s ease, box-shadow 0.3s ease !important;
    }
    
    .stCard:hover {
        transform: translateY(-5px) !important;
        box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* 按钮样式 */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
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
        background: rgba(255, 255, 255, 0.9) !important;
        border-radius: 12px !important;
        border: 2px solid rgba(102, 126, 234, 0.3) !important;
        padding: 1rem !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
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
        background: linear-gradient(90deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%) !important;
        border-radius: 10px !important;
        padding: 0.75rem 1rem !important;
        font-weight: 600 !important;
        border: 1px solid rgba(102, 126, 234, 0.2) !important;
    }
    
    .streamlit-expanderHeader:hover {
        background: linear-gradient(90deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%) !important;
    }
    
    /* 信息框样式 */
    .stAlert {
        border-radius: 12px !important;
        border-left: 4px solid #667eea !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1) !important;
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

# 导入KAG模块
from kag.common.conf import KAG_CONFIG
from kag.common.registry import import_modules_from_path
from kag.interface import ExtractorABC, LLMClient
from kag.builder.model.chunk import Chunk, ChunkTypeEnum
from kag.builder.model.sub_graph import SubGraph
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
            # 初始化KAG配置
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
                st.info("✅ 已加载军事部署专用Prompt")
            except ImportError as e:
                st.warning(f"⚠️ 无法导入自定义Prompt: {e}，将使用默认Prompt")
            
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
                st.warning("未找到extractor配置，使用schema_constraint_extractor（推荐使用schema）")
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
                    st.info(f"检测到 {extractor_type}，替换为 schema_constraint_extractor 以使用schema定义")
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
            
            # 验证抽取器类型
            extractor_type_name = type(extractor).__name__
            st.success(f"✅ 抽取器初始化成功: {extractor_type_name}")
            
            # 显示schema信息
            if hasattr(extractor, 'schema'):
                schema_types = list(extractor.schema.keys())
                entity_types = [t for t in schema_types if not t.startswith("_") and t not in ["Chunk", "AtomicQuery", "KnowledgeUnit", "Summary", "Outline", "Doc"]]
                st.info(f"📋 Schema中定义了 {len(entity_types)} 种实体类型: {', '.join(entity_types[:10])}{'...' if len(entity_types) > 10 else ''}")
            
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
                    progress_callback(1, 4, "步骤 1/4: 正在调用LLM进行实体识别...")
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
        <h1>🧠 KAG 知识抽取系统</h1>
        <p style="text-align: center; color: #666; font-size: 1.2rem; margin-top: -1rem;">
            <span style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
                🚀 智能知识图谱构建 | 实时抽取监控 | 可视化展示
            </span>
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    
    # 侧边栏配置
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0;">
            <h2 style="color: white; margin-bottom: 0.5rem;">⚙️ 系统配置</h2>
            <p style="color: rgba(255,255,255,0.8); font-size: 0.9rem;">知识抽取引擎控制中心</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 初始化抽取器
        if st.button("🔄 初始化抽取器", use_container_width=True, type="primary"):
            with st.spinner("🔄 正在初始化抽取器..."):
                st.session_state.extractor = init_extractor()
                if st.session_state.extractor:
                    st.success("✅ 抽取器初始化成功！")
                    st.balloons()  # 庆祝动画
                else:
                    st.error("❌ 抽取器初始化失败")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 状态指示器
        if st.session_state.extractor:
            st.markdown("""
            <div style="background: rgba(76, 175, 80, 0.2); padding: 1rem; border-radius: 10px; border-left: 4px solid #4caf50;">
                <p style="color: white; margin: 0; font-weight: 600;">✅ 抽取器已就绪</p>
                <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0 0 0; font-size: 0.9rem;">系统运行正常，可以开始抽取</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: rgba(255, 152, 0, 0.2); padding: 1rem; border-radius: 10px; border-left: 4px solid #ff9800;">
                <p style="color: white; margin: 0; font-weight: 600;">⚠️ 请先初始化抽取器</p>
                <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0 0 0; font-size: 0.9rem;">点击上方按钮初始化系统</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("""
        <div style="padding: 0.5rem 0;">
            <h3 style="color: white; margin-bottom: 1rem;">📚 使用指南</h3>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div style="background: rgba(255, 255, 255, 0.1); padding: 1rem; border-radius: 10px; color: white;">
            <p style="margin: 0.5rem 0;">1️⃣ 点击"初始化抽取器"按钮</p>
            <p style="margin: 0.5rem 0;">2️⃣ 在文本框中输入要抽取的文本</p>
            <p style="margin: 0.5rem 0;">3️⃣ 点击"开始抽取"按钮</p>
            <p style="margin: 0.5rem 0;">4️⃣ 查看抽取过程和结果</p>
        </div>
        """, unsafe_allow_html=True)
    
    # 主内容区
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        <div class="fade-in">
            <h2 style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
                📝 输入文本
            </h2>
        </div>
        """, unsafe_allow_html=True)
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
    
    with col2:
        st.markdown("""
        <div class="fade-in">
            <h2 style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
                📊 抽取统计
            </h2>
        </div>
        """, unsafe_allow_html=True)
        if st.session_state.current_result:
            result = st.session_state.current_result
            subgraph = result.get("subgraph")
            if subgraph:
                # 使用卡片样式包装统计信息
                st.markdown("""
                <div style="background: rgba(255, 255, 255, 0.95); padding: 1.5rem; border-radius: 15px; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);">
                """, unsafe_allow_html=True)
                stat1, stat2, stat3 = st.columns(3)
                with stat1:
                    st.metric("🎯 实体数量", len(subgraph.nodes), delta=None)
                with stat2:
                    st.metric("🔗 关系数量", len(subgraph.edges), delta=None)
                with stat3:
                    entity_types = len(set(n.label for n in subgraph.nodes))
                    st.metric("📋 实体类型", entity_types, delta=None)
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%); 
                        padding: 3rem 2rem; border-radius: 15px; text-align: center; border: 2px dashed rgba(102, 126, 234, 0.3);">
                <p style="font-size: 3rem; margin: 0;">👈</p>
                <p style="color: #666; font-size: 1.1rem; margin-top: 1rem;">请输入文本并开始抽取</p>
                <p style="color: #999; font-size: 0.9rem; margin-top: 0.5rem;">系统将自动识别实体和关系</p>
            </div>
            """, unsafe_allow_html=True)
    
    # 执行抽取
    if extract_button and input_text.strip():
        if not st.session_state.extractor:
            st.error("❌ 请先初始化抽取器！")
        else:
            # 创建可折叠的进度展示区域
            st.markdown("""
            <div style="margin: 2rem 0;">
                <h2 style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
                    🔄 实时抽取监控
                </h2>
            </div>
            """, unsafe_allow_html=True)
            with st.expander("📊 点击展开/收起查看详细进度", expanded=True):
                # 使用容器来组织进度显示
                progress_container = st.container()
                
                with progress_container:
                    # 进度条和状态
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    time_text = st.empty()
                    st.markdown("---")
                    
                    # 日志区域
                    st.markdown("""
                    <div style="margin-top: 1rem;">
                        <h4 style="color: #333; margin-bottom: 0.5rem;">
                            📋 实时日志
                        </h4>
                    </div>
                    """, unsafe_allow_html=True)
                    log_placeholder = st.empty()
                
                # 日志消息列表
                log_messages = []
                
                def update_progress(current, total, message):
                    """更新进度显示"""
                    nonlocal log_messages
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]  # 精确到毫秒
                    
                    # 更新进度条
                    progress_value = current / total if total > 0 else 0
                    progress_bar.progress(progress_value)
                    
                    # 更新状态文本（使用更酷炫的样式）
                    status_text.markdown(f"""
                    <div style="background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%); 
                                padding: 1rem; border-radius: 10px; border-left: 4px solid #667eea;">
                        <p style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #333;">
                            <span style="color: #667eea;">🔄</span> <strong>当前状态</strong>: {message}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    time_text.markdown(f"""
                    <p style="text-align: right; color: #999; font-size: 0.9rem; margin-top: 0.5rem;">
                        ⏰ 最后更新: <span style="color: #667eea; font-weight: 600;">{timestamp}</span>
                    </p>
                    """, unsafe_allow_html=True)
                    
                    # 添加日志
                    log_entry = f"[{timestamp}] {message}"
                    log_messages.append(log_entry)
                    
                    # 更新日志显示（只显示最近30条，避免太长）
                    with log_placeholder.container():
                        recent_logs = "\n".join(log_messages[-30:])
                        # 使用代码块显示日志，支持滚动，添加自定义样式
                        st.markdown(f"""
                        <div style="background: #1e1e1e; padding: 1rem; border-radius: 8px; max-height: 300px; overflow-y: auto;">
                            <pre style="color: #d4d4d4; font-family: 'Courier New', monospace; font-size: 0.9rem; margin: 0; white-space: pre-wrap; word-wrap: break-word;">
{recent_logs}
                            </pre>
                        </div>
                        """, unsafe_allow_html=True)
                
                # 执行抽取
                try:
                    subgraph, steps = extract_knowledge_step_by_step(
                        st.session_state.extractor,
                        input_text,
                        "用户输入",
                        progress_callback=update_progress
                    )
                    
                    # 最终状态更新
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    if subgraph:
                        progress_bar.progress(1.0)
                        status_text.markdown(f"""
                        <div style="background: linear-gradient(135deg, rgba(76, 175, 80, 0.2) 0%, rgba(76, 175, 80, 0.3) 100%); 
                                    padding: 1rem; border-radius: 10px; border-left: 4px solid #4caf50;">
                            <p style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #2e7d32;">
                                ✅ <strong>抽取完成！</strong> 识别了 <span style="color: #667eea;">{len(subgraph.nodes)}</span> 个实体和 
                                <span style="color: #667eea;">{len(subgraph.edges)}</span> 条关系
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                        log_messages.append(f"[{timestamp}] ✅ 抽取完成！")
                        st.balloons()  # 成功动画
                    else:
                        status_text.markdown("""
                        <div style="background: linear-gradient(135deg, rgba(255, 152, 0, 0.2) 0%, rgba(255, 152, 0, 0.3) 100%); 
                                    padding: 1rem; border-radius: 10px; border-left: 4px solid #ff9800;">
                            <p style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #f57c00;">
                                ⚠️ 抽取完成，但未生成图谱
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                        log_messages.append(f"[{timestamp}] ⚠️ 抽取完成，但未生成图谱")
                    
                    time_text.markdown(f"""
                    <p style="text-align: right; color: #999; font-size: 0.9rem; margin-top: 0.5rem;">
                        ⏰ 完成时间: <span style="color: #667eea; font-weight: 600;">{timestamp}</span>
                    </p>
                    """, unsafe_allow_html=True)
                    
                except Exception as e:
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    status_text.markdown(f"""
                    <div style="background: linear-gradient(135deg, rgba(244, 67, 54, 0.2) 0%, rgba(244, 67, 54, 0.3) 100%); 
                                padding: 1rem; border-radius: 10px; border-left: 4px solid #f44336;">
                        <p style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #c62828;">
                            ❌ <strong>抽取失败</strong>: {str(e)}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    log_messages.append(f"[{timestamp}] ❌ 错误: {str(e)}")
                    import traceback
                    error_details = traceback.format_exc()
                    log_messages.append(f"[{timestamp}] 详细错误:\n{error_details}")
                    st.error(f"抽取过程出错: {e}")
                    subgraph, steps = None, []
            
            # 显示抽取步骤（在可折叠区域中）
            if steps:
                st.markdown("""
                <div style="margin: 2rem 0;">
                    <h3 style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">
                        📋 抽取步骤详情
                    </h3>
                </div>
                """, unsafe_allow_html=True)
                with st.expander("🔍 点击查看详细步骤信息", expanded=False):
                    for step in steps:
                        step_status = step.get("status", "unknown")
                        status_icon = {
                            "completed": "✅",
                            "running": "🔄",
                            "error": "❌"
                        }.get(step_status, "⏳")
                        
                        # 根据状态设置颜色
                        status_color = {
                            "completed": "#4caf50",
                            "running": "#667eea",
                            "error": "#f44336"
                        }.get(step_status, "#999")
                        
                        st.markdown(f"""
                        <div style="background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%); 
                                    padding: 1rem; border-radius: 10px; border-left: 4px solid {status_color}; margin: 0.5rem 0;">
                            <p style="margin: 0; font-weight: 600; font-size: 1.1rem;">
                                {status_icon} <span style="color: {status_color};">步骤 {step['step']}: {step['name']}</span>
                            </p>
                            <p style="margin: 0.5rem 0 0 0; color: #666;">{step['description']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if step.get("entities"):
                            st.markdown("**🎯 识别的实体:**")
                            entity_cols = st.columns(min(4, len(step["entities"])))
                            for i, entity in enumerate(step["entities"]):
                                with entity_cols[i % 4]:
                                    st.markdown(f"""
                                    <div style="background: rgba(102, 126, 234, 0.1); padding: 0.75rem; border-radius: 8px; 
                                                border-left: 3px solid #667eea; margin: 0.25rem 0;">
                                        <p style="margin: 0; font-weight: 600; color: #333;">{entity['name']}</p>
                                        <p style="margin: 0.25rem 0 0 0; font-size: 0.85rem; color: #667eea;">{entity['type']}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                        
                        if step.get("relations"):
                            st.markdown("**🔗 抽取的关系:**")
                            for rel in step["relations"][:10]:  # 限制显示
                                st.markdown(f"""
                                <div style="background: #1e1e1e; padding: 0.75rem; border-radius: 8px; margin: 0.5rem 0;">
                                    <code style="color: #4caf50; font-size: 0.9rem;">
                                        {rel['from']} <span style="color: #667eea;">--[{rel['label']}]--></span> {rel['to']}
                                    </code>
                                </div>
                                """, unsafe_allow_html=True)
                        
                        st.markdown("<br>", unsafe_allow_html=True)
            
            # 保存结果
            if subgraph:
                st.session_state.current_result = {
                    "subgraph": subgraph,
                    "source_text": input_text,
                    "steps": steps,
                    "timestamp": time.time()
                }
                st.markdown("""
                <div style="background: linear-gradient(135deg, rgba(76, 175, 80, 0.2) 0%, rgba(76, 175, 80, 0.3) 100%); 
                            padding: 1rem; border-radius: 10px; border-left: 4px solid #4caf50; margin: 1rem 0;">
                    <p style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #2e7d32;">
                        ✅ 抽取成功！结果已生成。
                    </p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="background: linear-gradient(135deg, rgba(255, 152, 0, 0.2) 0%, rgba(255, 152, 0, 0.3) 100%); 
                            padding: 1rem; border-radius: 10px; border-left: 4px solid #ff9800; margin: 1rem 0;">
                    <p style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #f57c00;">
                        ⚠️ 抽取完成，但未生成图谱。
                    </p>
                </div>
                """, unsafe_allow_html=True)
    
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
                <p style="text-align: center; color: #666; margin-top: -0.5rem;">
                    交互式图谱展示 | 实体关系可视化 | 原文高亮对应
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # 生成可视化
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
                
                # 显示HTML文件（添加边框和阴影效果）
                st.markdown("""
                <div style="background: white; padding: 1rem; border-radius: 15px; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2); margin: 1rem 0;">
                """, unsafe_allow_html=True)
                
                with open(output_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                st.components.v1.html(html_content, height=800, scrolling=True)
                
                st.markdown("</div>", unsafe_allow_html=True)
                
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


if __name__ == "__main__":
    main()

