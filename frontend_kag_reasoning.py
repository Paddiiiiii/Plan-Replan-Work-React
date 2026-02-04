import streamlit as st
import requests
import time

API_TIMEOUT = 1800

def render_kag_reasoning_tab(api_url: str):
    """渲染知识抽取推理标签页"""
    st.header("🧠 知识抽取 知识推理")
    st.markdown("输入您的问题，系统将基于知识图谱进行推理并返回答案及溯源信息。")
    
    if "kag_query_history" not in st.session_state:
        st.session_state.kag_query_history = []
    if "kag_last_result" not in st.session_state:
        st.session_state.kag_last_result = None
    
    col1, col2 = st.columns([4, 1])
    with col1:
        question = st.text_area(
            "请输入您的问题",
            height=100,
            placeholder="例如：轻步兵应该部署在什么位置？",
            key="kag_question_input"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        query_button = st.button("🔍 开始推理", type="primary", use_container_width=True)
        clear_button = st.button("🗑️ 清空", use_container_width=True)
    
    if clear_button:
        st.session_state.kag_query_history = []
        st.session_state.kag_last_result = None
        st.rerun()
    
    if query_button and question.strip():
        with st.spinner("正在推理中，请稍候..."):
            try:
                response = requests.post(
                    f"{api_url}/api/kag/query",
                    json={"question": question.strip()},
                    timeout=API_TIMEOUT
                )
                
                if response.status_code == 200:
                    result = response.json()
                    st.session_state.kag_last_result = result
                    st.session_state.kag_query_history.append({
                        "question": question.strip(),
                        "result": result,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    st.rerun()
                else:
                    error_msg = response.json().get("detail", f"请求失败: {response.status_code}")
                    st.error(f"推理失败: {error_msg}")
            except requests.exceptions.RequestException as e:
                st.error(f"连接API失败: {e}")
                st.info("请确保后端服务已启动（运行 main.py）")
            except Exception as e:
                st.error(f"推理过程出错: {str(e)}")
    
    if st.session_state.kag_last_result:
        result = st.session_state.kag_last_result
        
        if result.get("success", False):
            st.markdown("---")
            st.subheader("📝 推理答案")
            answer = result.get("answer", "")
            if answer:
                st.markdown(f"**答案：**\n\n{answer}")
            else:
                st.warning("未返回答案")
            
            source_texts = result.get("source_texts", [])
            if source_texts:
                st.markdown("---")
                st.subheader("📄 检索原文")
                st.markdown("以下是知识抽取检索到的原始文档片段，用于生成答案：")
                for idx, source in enumerate(source_texts, 1):
                    source_text = source.get("text", str(source))
                    source_metadata = source.get("metadata", {})
                    source_type = source.get("source", "未知来源")
                    
                    with st.expander(f"原文 {idx} ({source_type}): {source_text[:80]}..." if len(source_text) > 80 else f"原文 {idx} ({source_type}): {source_text}", expanded=True):
                        st.markdown(f"**原文内容：**")
                        st.text_area(
                            f"原文 {idx}",
                            value=source_text,
                            height=min(300, max(100, len(source_text) // 3)),
                            key=f"source_text_{idx}",
                            label_visibility="collapsed"
                        )
                        if source_metadata:
                            st.markdown("**元数据：**")
                            st.json(source_metadata)
            else:
                st.info("未获取到检索原文（可能知识抽取未返回检索结果）")
            
            references = result.get("references", [])
            if references:
                st.markdown("---")
                st.subheader("📚 引用来源")
                for idx, ref in enumerate(references, 1):
                    if isinstance(ref, dict):
                        ref_text = ref.get("text", str(ref))
                        ref_metadata = ref.get("metadata", {})
                        with st.expander(f"引用 {idx}: {ref_text[:100]}..." if len(ref_text) > 100 else f"引用 {idx}: {ref_text}", expanded=False):
                            st.markdown(f"**内容：**\n\n{ref_text}")
                            if ref_metadata:
                                st.markdown("**元数据：**")
                                st.json(ref_metadata)
                    else:
                        st.markdown(f"**引用 {idx}：** {ref}")
            
            tasks = result.get("tasks", [])
            if tasks:
                st.markdown("---")
                st.subheader("🔍 推理溯源")
                st.markdown("以下是推理过程中执行的任务，展示了答案的生成过程：")
                
                for idx, task in enumerate(tasks, 1):
                    task_info = task.get("task", {})
                    task_result = task.get("result", "")
                    task_memory = task.get("memory", {})
                    executor = task.get("executor", "未知")
                    
                    with st.expander(f"任务 {idx}: {executor}", expanded=False):
                        if task_info:
                            st.markdown("**任务参数：**")
                            st.json(task_info)
                        
                        if task_result:
                            st.markdown("**任务结果：**")
                            if isinstance(task_result, str):
                                try:
                                    import json
                                    parsed_result = json.loads(task_result)
                                    st.json(parsed_result)
                                except:
                                    st.text(task_result)
                            else:
                                st.json(task_result)
                        
                        if task_memory:
                            st.markdown("**任务上下文：**")
                            st.json(task_memory)
            
            if st.session_state.kag_query_history:
                st.markdown("---")
                st.subheader("📜 查询历史")
                for idx, history_item in enumerate(st.session_state.kag_query_history, 1):
                    with st.expander(f"查询 {idx}: {history_item['question'][:50]}... ({history_item['timestamp']})", expanded=False):
                        st.markdown(f"**问题：** {history_item['question']}")
                        st.markdown(f"**时间：** {history_item['timestamp']}")
                        
                        history_result = history_item.get("result", {})
                        if history_result.get("success"):
                            st.markdown(f"**答案：** {history_result.get('answer', '无')}")
                        else:
                            st.error(f"失败: {history_result.get('error', '未知错误')}")
        else:
            st.error(f"推理失败: {result.get('error', '未知错误')}")
