'''
Author: ZhangLe
Date: 2026-01-15 17:28:37
Version: 0.0.1
Content: 
'''
import streamlit as st
import os

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from frontend_utils import get_server_ip

try:
    st.set_page_config(
        page_title="部署智能体",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

SERVER_IP = get_server_ip()
API_URL = f"http://{SERVER_IP}:8000"

from frontend_agent_task import render_agent_task_tab
from frontend_history_results import render_history_results_tab
from frontend_entity_relation_graph import render_entity_relation_graph_tab
from frontend_kag_reasoning import render_kag_reasoning_tab

def main():
    st.title("🤖 部署智能体系统")
    
    st.info(
        f"📚 **API文档**: [Swagger UI]({API_URL}/docs) | [ReDoc]({API_URL}/redoc) | "
        f"**API地址**: {API_URL}"
    )
    
    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(["智能体任务", "历史结果", "实体-关系图", "KAG推理"])

    with tab1:
        render_agent_task_tab(API_URL)

    with tab2:
        render_history_results_tab(API_URL)

    with tab3:
        render_entity_relation_graph_tab(API_URL)

    with tab4:
        render_kag_reasoning_tab(API_URL)

if __name__ == "__main__":
    main()
