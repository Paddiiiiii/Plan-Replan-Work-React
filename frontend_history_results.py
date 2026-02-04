import streamlit as st
import requests
import os
from config import HISTORY_DISPLAY_CONFIG, PATHS
from frontend_utils import load_geojson, create_map, parse_regions_from_task, format_filter_params

def render_history_results_tab(api_url: str):
    """渲染历史结果标签页"""
    st.header("历史结果")

    if "results_list" not in st.session_state:
        st.session_state.results_list = None
    if "results_refresh_key" not in st.session_state:
        st.session_state.results_refresh_key = 0
    if "selected_result_file" not in st.session_state:
        st.session_state.selected_result_file = None

    col1, col2 = st.columns([2, 1])
    with col2:
        if st.button("刷新列表", key="refresh_results"):
            st.session_state.results_list = None
            st.session_state.selected_result_file = None
            st.session_state.results_refresh_key += 1
            st.rerun()

    if st.session_state.results_list is None:
        with st.spinner("正在加载结果文件列表..."):
            try:
                response = requests.get(
                    f"{api_url}/api/results",
                    timeout=30
                )
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        st.session_state.results_list = result.get("results", [])
                    else:
                        st.error("获取结果列表失败")
                        st.session_state.results_list = []
                else:
                    st.error(f"API请求失败: {response.status_code}")
                    st.session_state.results_list = []
            except requests.exceptions.RequestException as e:
                st.error(f"连接API失败: {e}")
                st.info("请确保后端服务已启动（运行 main.py）")
                st.session_state.results_list = []

    if st.session_state.results_list:
        if len(st.session_state.results_list) > 0:
            result_options = {f"{r['filename']} ({r['modified_time_str']})": r['filename']
                              for r in st.session_state.results_list}
            selected_display = st.selectbox(
                "选择结果文件",
                options=list(result_options.keys()),
                index=list(result_options.values()).index(st.session_state.selected_result_file) if st.session_state.selected_result_file in result_options.values() else 0,
                key="select_result_file"
            )

            load_button_pressed = st.button("加载结果", type="primary", key="load_result_button")

            if selected_display:
                selected_filename = result_options[selected_display]
                if selected_filename != st.session_state.selected_result_file:
                    st.session_state.selected_result_file = selected_filename
                    if "loaded_result_data" in st.session_state and selected_filename in st.session_state.loaded_result_data:
                        del st.session_state.loaded_result_data[selected_filename]
                    if "loaded_result_metadata" in st.session_state and selected_filename in st.session_state.loaded_result_metadata:
                        del st.session_state.loaded_result_metadata[selected_filename]

            if "loaded_result_data" not in st.session_state:
                st.session_state.loaded_result_data = {}
            if "loaded_result_metadata" not in st.session_state:
                st.session_state.loaded_result_metadata = {}

            if load_button_pressed and selected_filename and selected_filename not in st.session_state.loaded_result_data:
                with st.spinner("正在加载结果文件..."):
                    try:
                        from urllib.parse import quote
                        encoded_filename = quote(selected_filename, safe='')
                        response = requests.get(
                            f"{api_url}/api/results/{encoded_filename}",
                            timeout=30
                        )
                        if response.status_code == 200:
                            import tempfile
                            with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as tmp_file:
                                tmp_file.write(response.text)
                                tmp_path = tmp_file.name

                            gdf = load_geojson(tmp_path)

                            try:
                                os.unlink(tmp_path)
                            except:
                                pass

                            if gdf is not None:
                                st.session_state.loaded_result_data[selected_filename] = gdf

                                metadata = None
                                try:
                                    metadata_response = requests.get(
                                        f"{api_url}/api/results/{encoded_filename}/metadata",
                                        timeout=30
                                    )
                                    if metadata_response.status_code == 200:
                                        metadata_result = metadata_response.json()
                                        if metadata_result.get("success"):
                                            metadata = metadata_result.get("metadata", {})
                                            st.session_state.loaded_result_metadata[selected_filename] = metadata
                                except:
                                    st.session_state.loaded_result_metadata[selected_filename] = None
                                    pass

                                if selected_filename in st.session_state.loaded_result_data:
                                    gdf = st.session_state.loaded_result_data[selected_filename]
                                    metadata = st.session_state.loaded_result_metadata.get(selected_filename)
                                else:
                                    gdf = None
                                    metadata = None

                                if gdf is not None:
                                    st.subheader("地图显示")
                                    regions = []
                                    if metadata:
                                        regions = metadata.get("regions", [])
                                        if not regions:
                                            original_query = metadata.get("original_query", "")
                                            if original_query:
                                                try:
                                                    regions = parse_regions_from_task(original_query)
                                                except:
                                                    pass
                                    
                                    formatted_regions = []
                                    for region in regions:
                                        if isinstance(region, dict):
                                            top_left = region.get("top_left")
                                            bottom_right = region.get("bottom_right")
                                            if isinstance(top_left, list):
                                                top_left = tuple(top_left)
                                            if isinstance(bottom_right, list):
                                                bottom_right = tuple(bottom_right)
                                            formatted_regions.append({
                                                "name": region.get("name", ""),
                                                "top_left": top_left,
                                                "bottom_right": bottom_right
                                            })
                                    
                                    reference_points = []
                                    if metadata and metadata.get("reference_points"):
                                        for ref_info in metadata.get("reference_points", []):
                                            if isinstance(ref_info, dict):
                                                point = ref_info.get("point", {})
                                                direction = ref_info.get("direction")
                                                if isinstance(point, dict) and point.get("lon") is not None and point.get("lat") is not None:
                                                    reference_points.append({
                                                        "point": point,
                                                        "direction": direction
                                                    })
                                    
                                    if HISTORY_DISPLAY_CONFIG.get("show_map", True):
                                        m = create_map(gdf, reference_points=reference_points if reference_points else None, regions=formatted_regions if formatted_regions else None)
                                        if m:
                                            st.components.v1.html(m._repr_html_(), height=600)

                                    st.subheader("数据统计")
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("区域数量", len(gdf))
                                    with col2:
                                        total_area = gdf['area_m2'].sum() if 'area_m2' in gdf.columns else 0
                                        st.metric("总面积 (m²)", f"{total_area:,.0f}")
                                    with col3:
                                        total_area_km2 = gdf['area_km2'].sum() if 'area_km2' in gdf.columns else 0
                                        st.metric("总面积 (km²)", f"{total_area_km2:,.2f}")
                                    
                                    if metadata:
                                        st.markdown("---")
                                        
                                        if HISTORY_DISPLAY_CONFIG.get("show_regions", True):
                                            filter_params_list = metadata.get("filter_params", [])
                                            if filter_params_list:
                                                st.subheader("筛选参数")
                                                for item in filter_params_list:
                                                    st.markdown(f"**步骤 {item['step']} - {item.get('tool_display_name', item.get('tool', ''))}**")
                                                    for key, value in item.get('params', {}).items():
                                                        st.write(f"  • **{key}**: {value}")
                                                    if item != filter_params_list[-1]:
                                                        st.markdown("---")
                                            else:
                                                st.subheader("筛选参数")
                                                st.info("无筛选参数信息")
                                        
                                        if HISTORY_DISPLAY_CONFIG.get("show_llm_thinking", True):
                                            st.markdown("---")
                                            with st.expander("📋 知识抽取问答结果与大模型思考过程", expanded=True):
                                                kag_qa_results = metadata.get("kag_qa_results", [])
                                                if kag_qa_results:
                                                    st.subheader("知识抽取知识召回结果")
                                                    st.write(f"共{len(kag_qa_results)}个问题：")
                                                    for i, qa_result in enumerate(kag_qa_results, 1):
                                                        question = qa_result.get("question", "")
                                                        answer = qa_result.get("answer", "")
                                                        st.markdown(f"**问题{i}**: {question}")
                                                        st.markdown(f"**答案{i}**: {answer}")
                                                        st.markdown("---")
                                                
                                                if metadata.get("first_llm_response"):
                                                    st.subheader("第一轮大模型思考（工具选择和参数提取）")
                                                    first_response = metadata.get("first_llm_response", "")
                                                    MAX_RESPONSE_LENGTH = 50000
                                                    if len(first_response) > MAX_RESPONSE_LENGTH:
                                                        st.warning(f"⚠️ 大模型响应较长（{len(first_response)}字符），仅显示前{MAX_RESPONSE_LENGTH}字符")
                                                        first_response = first_response[:MAX_RESPONSE_LENGTH] + "\n\n...（内容已截断）"
                                                    st.text_area(
                                                        "第一轮大模型响应",
                                                        value=first_response,
                                                        height=200,
                                                        key=f"first_llm_response_history_{selected_filename}",
                                                        label_visibility="collapsed"
                                                    )
                                                
                                                if metadata.get("second_llm_response"):
                                                    st.subheader("第二轮大模型思考（工具调用计划编织）")
                                                    second_response = metadata.get("second_llm_response", "")
                                                    if len(second_response) > MAX_RESPONSE_LENGTH:
                                                        st.warning(f"⚠️ 大模型响应较长（{len(second_response)}字符），仅显示前{MAX_RESPONSE_LENGTH}字符")
                                                        second_response = second_response[:MAX_RESPONSE_LENGTH] + "\n\n...（内容已截断）"
                                                    st.text_area(
                                                        "第二轮大模型响应",
                                                        value=second_response,
                                                        height=200,
                                                        key=f"second_llm_response_history_{selected_filename}",
                                                        label_visibility="collapsed"
                                                    )
                                        
                                        if HISTORY_DISPLAY_CONFIG.get("show_kg_graph", True):
                                            kg_graph_image_filename = metadata.get("kg_graph_image_filename")
                                            retrieved_entities = metadata.get("retrieved_entities", [])
                                            retrieved_relations = metadata.get("retrieved_relations", [])
                                            
                                            if kg_graph_image_filename:
                                                st.markdown("---")
                                                st.subheader("实体关系图")
                                                try:
                                                    from urllib.parse import quote
                                                    encoded_image_filename = quote(kg_graph_image_filename, safe='')
                                                    image_response = requests.get(
                                                        f"{api_url}/api/kg-graph-images/{encoded_image_filename}",
                                                        timeout=30
                                                    )
                                                    if image_response.status_code == 200:
                                                        st.image(image_response.content, caption="实体关系图", use_container_width=True)
                                                    else:
                                                        st.warning(f"无法加载图片: {kg_graph_image_filename}")
                                                except Exception as e:
                                                    st.warning(f"加载图片失败: {e}")
                                            elif retrieved_entities or retrieved_relations:
                                                st.markdown("---")
                                                with st.expander("🔍 知识抽取检索到的实体和关系", expanded=False):
                                                    from frontend_entity_relation_graph import display_kag_entities_relations
                                                    display_kag_entities_relations(retrieved_entities, retrieved_relations)
                                    else:
                                        st.error("加载GeoJSON文件失败")
                        else:
                            st.error(f"API请求失败: {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"连接API失败: {e}")
                        st.info("请确保后端服务已启动（运行 main.py）")
            elif selected_filename in st.session_state.loaded_result_data:
                gdf = st.session_state.loaded_result_data[selected_filename]
                metadata = st.session_state.loaded_result_metadata.get(selected_filename)

                if gdf is not None:
                    st.subheader("地图显示")
                    regions = []
                    if metadata:
                        regions = metadata.get("regions", [])
                        if not regions:
                            original_query = metadata.get("original_query", "")
                            if original_query:
                                try:
                                    regions = parse_regions_from_task(original_query)
                                except:
                                    pass
                    
                    formatted_regions = []
                    for region in regions:
                        if isinstance(region, dict):
                            top_left = region.get("top_left")
                            bottom_right = region.get("bottom_right")
                            if isinstance(top_left, list):
                                top_left = tuple(top_left)
                            if isinstance(bottom_right, list):
                                bottom_right = tuple(bottom_right)
                            formatted_regions.append({
                                "name": region.get("name", ""),
                                "top_left": top_left,
                                "bottom_right": bottom_right
                            })
                    
                    reference_points = []
                    if metadata and metadata.get("reference_points"):
                        for ref_info in metadata.get("reference_points", []):
                            if isinstance(ref_info, dict):
                                point = ref_info.get("point", {})
                                direction = ref_info.get("direction")
                                if isinstance(point, dict) and point.get("lon") is not None and point.get("lat") is not None:
                                    reference_points.append({
                                        "point": point,
                                        "direction": direction
                                    })
                    
                    if HISTORY_DISPLAY_CONFIG.get("show_map", True):
                        m = create_map(gdf, reference_points=reference_points if reference_points else None, regions=formatted_regions if formatted_regions else None)
                        if m:
                            st.components.v1.html(m._repr_html_(), height=600)

                    st.subheader("数据统计")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("区域数量", len(gdf))
                    with col2:
                        total_area = gdf['area_m2'].sum() if 'area_m2' in gdf.columns else 0
                        st.metric("总面积 (m²)", f"{total_area:,.0f}")
                    with col3:
                        total_area_km2 = gdf['area_km2'].sum() if 'area_km2' in gdf.columns else 0
                        st.metric("总面积 (km²)", f"{total_area_km2:,.2f}")
                    
                    if metadata:
                        st.markdown("---")
                        
                        if HISTORY_DISPLAY_CONFIG.get("show_regions", True):
                            filter_params_list = metadata.get("filter_params", [])
                            if filter_params_list:
                                st.subheader("筛选参数")
                                for item in filter_params_list:
                                    st.markdown(f"**步骤 {item['step']} - {item.get('tool_display_name', item.get('tool', ''))}**")
                                    for key, value in item.get('params', {}).items():
                                        st.write(f"  • **{key}**: {value}")
                                    if item != filter_params_list[-1]:
                                        st.markdown("---")
                            else:
                                st.subheader("筛选参数")
                                st.info("无筛选参数信息")
                        
                        if HISTORY_DISPLAY_CONFIG.get("show_llm_thinking", True):
                            st.markdown("---")
                            with st.expander("📋 知识抽取问答结果与大模型思考过程", expanded=True):
                                kag_qa_results = metadata.get("kag_qa_results", [])
                                if kag_qa_results:
                                    st.subheader("知识抽取知识召回结果")
                                    st.write(f"共{len(kag_qa_results)}个问题：")
                                    for i, qa_result in enumerate(kag_qa_results, 1):
                                        question = qa_result.get("question", "")
                                        answer = qa_result.get("answer", "")
                                        st.markdown(f"**问题{i}**: {question}")
                                        st.markdown(f"**答案{i}**: {answer}")
                                        st.markdown("---")
                                
                                if metadata.get("first_llm_response"):
                                    st.subheader("第一轮大模型思考（工具选择和参数提取）")
                                    first_response = metadata.get("first_llm_response", "")
                                    MAX_RESPONSE_LENGTH = 50000
                                    if len(first_response) > MAX_RESPONSE_LENGTH:
                                        st.warning(f"⚠️ 大模型响应较长（{len(first_response)}字符），仅显示前{MAX_RESPONSE_LENGTH}字符")
                                        first_response = first_response[:MAX_RESPONSE_LENGTH] + "\n\n...（内容已截断）"
                                    st.text_area(
                                        "第一轮大模型响应",
                                        value=first_response,
                                        height=200,
                                        key=f"first_llm_response_history_{selected_filename}",
                                        label_visibility="collapsed"
                                    )
                                
                                if metadata.get("second_llm_response"):
                                    st.subheader("第二轮大模型思考（工具调用计划编织）")
                                    second_response = metadata.get("second_llm_response", "")
                                    if len(second_response) > MAX_RESPONSE_LENGTH:
                                        st.warning(f"⚠️ 大模型响应较长（{len(second_response)}字符），仅显示前{MAX_RESPONSE_LENGTH}字符")
                                        second_response = second_response[:MAX_RESPONSE_LENGTH] + "\n\n...（内容已截断）"
                                    st.text_area(
                                        "第二轮大模型响应",
                                        value=second_response,
                                        height=200,
                                        key=f"second_llm_response_history_{selected_filename}",
                                        label_visibility="collapsed"
                                    )
                        
                        if HISTORY_DISPLAY_CONFIG.get("show_kg_graph", True):
                            kg_graph_image_filename = metadata.get("kg_graph_image_filename")
                            retrieved_entities = metadata.get("retrieved_entities", [])
                            retrieved_relations = metadata.get("retrieved_relations", [])
                            
                            if kg_graph_image_filename:
                                st.markdown("---")
                                st.subheader("实体关系图")
                                try:
                                    from urllib.parse import quote
                                    encoded_image_filename = quote(kg_graph_image_filename, safe='')
                                    image_response = requests.get(
                                        f"{api_url}/api/kg-graph-images/{encoded_image_filename}",
                                        timeout=30
                                    )
                                    if image_response.status_code == 200:
                                        st.image(image_response.content, caption="实体关系图", use_container_width=True)
                                    else:
                                        st.warning(f"无法加载图片: {kg_graph_image_filename}")
                                except Exception as e:
                                    st.warning(f"加载图片失败: {e}")
                            elif retrieved_entities or retrieved_relations:
                                st.markdown("---")
                                with st.expander("🔍 知识抽取检索到的实体和关系", expanded=False):
                                    from frontend_entity_relation_graph import display_kag_entities_relations
                                    display_kag_entities_relations(retrieved_entities, retrieved_relations)
        else:
            st.info("暂无结果文件")
