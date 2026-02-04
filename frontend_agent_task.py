import streamlit as st
import requests
from typing import Dict
from frontend_utils import load_geojson, create_map, parse_regions_from_task, format_filter_params

API_TIMEOUT = 1800

def _display_result(sub_result: Dict, plan: Dict):
    """显示单个子结果（用于多任务模式）"""
    unit = sub_result.get("unit", "未知单位")
    result_path = sub_result.get("result_path")
    steps = sub_result.get("steps", [])
    
    if not sub_result.get("success", False):
        st.error(f"{unit} 执行失败: {sub_result.get('error', '未知错误')}")
        return
    
    if not result_path:
        st.warning(f"{unit} 未生成结果文件")
        return
    
    gdf = load_geojson(result_path)
    if gdf is None:
        st.error(f"{unit} 无法加载结果文件")
        return
    
    st.subheader(f"{unit} - 结果地图")
    reference_points = []
    for step_result in steps:
        if step_result.get("success") and step_result.get("tool") == "relative_position_filter_tool":
            step_params = step_result.get("params", {})
            result_data = step_result.get("result", {})
            ref_point = None
            ref_dir = None
            if result_data.get("reference_point"):
                ref_point = result_data.get("reference_point")
            elif step_params.get("reference_point"):
                ref_point = step_params.get("reference_point")
            if result_data.get("reference_direction") is not None:
                ref_dir = result_data.get("reference_direction")
            elif step_params.get("reference_direction") is not None:
                ref_dir = step_params.get("reference_direction")
            
            if ref_point and ref_dir is not None:
                reference_points.append({"point": ref_point, "direction": ref_dir})
    
    regions = st.session_state.get("regions", [])
    if not regions and plan:
        original_query = plan.get("original_query", "")
        if original_query:
            regions = parse_regions_from_task(original_query)
    
    m = create_map(gdf, reference_points=reference_points, regions=regions)
    if m:
        st.components.v1.html(m._repr_html_(), height=600)
    
    st.subheader(f"{unit} - 统计信息")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("区域数量", len(gdf))
    with col2:
        total_area = gdf['area_m2'].sum() if 'area_m2' in gdf.columns else 0
        st.metric("总面积 (m²)", f"{total_area:,.0f}")
    with col3:
        total_area_km2 = gdf['area_km2'].sum() if 'area_km2' in gdf.columns else 0
        st.metric("总面积 (km²)", f"{total_area_km2:,.2f}")
    
    st.subheader(f"{unit} - 筛选参数")
    
    default_tools = []
    tool_name_map = {
        "buffer_filter_tool": "缓冲区筛选",
        "elevation_filter_tool": "高程筛选",
        "slope_filter_tool": "坡度筛选",
        "vegetation_filter_tool": "植被筛选",
        "distance_filter_tool": "距离筛选",
        "area_filter_tool": "面积筛选",
        "relative_position_filter_tool": "相对位置筛选"
    }
    
    for step_result in steps:
        if step_result.get("success") and step_result.get("is_default", False):
            tool_name = step_result.get("tool", "")
            if tool_name in tool_name_map:
                default_tools.append(tool_name_map[tool_name])
    
    filter_params_list = format_filter_params(steps)
    
    if filter_params_list:
        for item in filter_params_list:
            st.markdown(f"**步骤 {item['step']} - {item['tool_display_name']}**")
            for key, value in item['params'].items():
                st.write(f"  • **{key}**: {value}")
            if item != filter_params_list[-1]:
                st.markdown("---")
    
    if default_tools:
        st.info(f"{'、'.join(default_tools)}工具已通过默认值调用")
    
    if not filter_params_list and not default_tools:
        st.info("无筛选参数信息")
    
    if plan:
        st.markdown("---")
        with st.expander("📋 知识抽取问答结果与检索信息", expanded=False):
            if plan.get("kag_results"):
                st.subheader("知识抽取知识召回结果")
                kag_results = plan.get("kag_results", [])
                st.write(f"共{len(kag_results)}个问题：")
                for i, kag_result in enumerate(kag_results, 1):
                    question = kag_result.get("question", "")
                    answer = kag_result.get("answer", "")
                    st.markdown(f"**问题{i}**: {question}")
                    st.markdown(f"**答案{i}**: {answer}")
                    st.markdown("---")
            
            retrieved_entities = plan.get("retrieved_entities", [])
            retrieved_relations = plan.get("retrieved_relations", [])
            
            if not retrieved_entities and not retrieved_relations and plan.get("kag_results"):
                for kag_result in plan.get("kag_results", []):
                    tasks = kag_result.get("tasks", [])
                    for task in tasks:
                        task_memory = task.get("memory", {})
                        if "retriever" in task_memory:
                            retriever_output = task_memory["retriever"]
                            if isinstance(retriever_output, dict):
                                graph_data = retriever_output.get("graph_data") or retriever_output.get("kg_graph")
                                if graph_data and isinstance(graph_data, dict):
                                    nodes = graph_data.get("nodes", graph_data.get("resultNodes", []))
                                    for node in nodes:
                                        if isinstance(node, dict):
                                            entity_id = node.get("id") or node.get("name", "")
                                            if entity_id and not any(e.get("id") == entity_id for e in retrieved_entities):
                                                retrieved_entities.append({
                                                    "id": entity_id,
                                                    "name": node.get("name", entity_id),
                                                    "type": node.get("type") or node.get("label", "Unknown"),
                                                    "properties": node.get("properties", {})
                                                })
                                    edges = graph_data.get("edges", graph_data.get("resultEdges", []))
                                    for edge in edges:
                                        if isinstance(edge, dict):
                                            source = edge.get("from_id") or edge.get("from") or edge.get("source", "")
                                            target = edge.get("to_id") or edge.get("to") or edge.get("target", "")
                                            if source and target:
                                                if not any(r.get("source") == source and r.get("target") == target and r.get("type") == edge.get("label", edge.get("type", "")) for r in retrieved_relations):
                                                    retrieved_relations.append({
                                                        "source": source,
                                                        "target": target,
                                                        "type": edge.get("label") or edge.get("type", "Unknown"),
                                                        "properties": edge.get("properties", {})
                                                    })
            
            if retrieved_entities or retrieved_relations:
                st.markdown("---")
                from frontend_entity_relation_graph import display_kag_entities_relations
                display_kag_entities_relations(retrieved_entities, retrieved_relations)

def render_agent_task_tab(api_url: str):
    """渲染智能体任务标签页"""
    st.header("智能体任务流程")

    if "current_plan" not in st.session_state:
        st.session_state.current_plan = None
    if "current_stage" not in st.session_state:
        st.session_state.current_stage = "input"
    if "task_input" not in st.session_state:
        st.session_state.task_input = "我已知一个迫击炮排和一个装甲反坦克排的位置，帮我找基指的位置。迫击炮排坐标： (118.519, 31.5515)，装甲反坦克排坐标： (118.560, 31.5520)"
    if "regions" not in st.session_state:
        st.session_state.regions = [
            {
                "name": "后方保障区",
                "top_left": (118.480, 31.500),
                "bottom_right": (118.572, 31.500)
            },
            { 
                "name": "调整线S",
                "top_left": (118.480, 31.5518),
                "bottom_right": (118.572, 31.5518)
            },
            {
                "name": "调整线P",
                "top_left": (118.480, 31.536),
                "bottom_right": (118.572, 31.536)
            },
            {
                "name": "前沿区域",
                "top_left": (118.480, 31.581),
                "bottom_right": (118.572, 31.581)
            }
        ]
    if "execution_completed" not in st.session_state:
        st.session_state.execution_completed = False

    if st.session_state.current_stage == "input":
        st.subheader("📝 任务描述")
        task_input = st.text_area(
            "输入任务描述",
            value=st.session_state.task_input,
            height=150,
            key="task_input_area",
            help="在此输入您的任务描述，例如：我已知一个迫击炮排和一个装甲反坦克排的位置，帮我找基指的位置。"
        )
        
        st.markdown("---")
        
        st.subheader("🗺️ 绘画需要（区域信息）")
        st.caption("在此输入需要在地图上绘制的区域信息（可选）")
        
        regions = st.session_state.regions.copy() if st.session_state.regions else []
        
        updated_regions = []
        for idx, region in enumerate(regions):
            with st.container():
                st.markdown(f"**区域 {idx + 1}**")
                col_name, col_del = st.columns([5, 1])
                with col_name:
                    region_name = st.text_input(
                        "区域名称",
                        value=region.get("name", ""),
                        key=f"region_name_{idx}",
                        placeholder="例如：前沿区域"
                    )
                with col_del:
                    st.write("")
                    st.write("")
                    if st.button("🗑️", key=f"delete_region_{idx}", help="删除此区域"):
                        st.session_state.regions = [r for i, r in enumerate(regions) if i != idx]
                        st.rerun()
                
                col_tl, col_br = st.columns(2)
                with col_tl:
                    top_left_lon = st.number_input(
                        "左上角经度",
                        value=float(region.get("top_left", (0, 0))[0]) if region.get("top_left") else 0.0,
                        key=f"top_left_lon_{idx}",
                        format="%.6f"
                    )
                    top_left_lat = st.number_input(
                        "左上角纬度",
                        value=float(region.get("top_left", (0, 0))[1]) if region.get("top_left") else 0.0,
                        key=f"top_left_lat_{idx}",
                        format="%.6f"
                    )
                with col_br:
                    bottom_right_lon = st.number_input(
                        "右下角经度",
                        value=float(region.get("bottom_right", (0, 0))[0]) if region.get("bottom_right") else 0.0,
                        key=f"bottom_right_lon_{idx}",
                        format="%.6f"
                    )
                    bottom_right_lat = st.number_input(
                        "右下角纬度",
                        value=float(region.get("bottom_right", (0, 0))[1]) if region.get("bottom_right") else 0.0,
                        key=f"bottom_right_lat_{idx}",
                        format="%.6f"
                    )
                
                updated_regions.append({
                    "name": region_name,
                    "top_left": (top_left_lon, top_left_lat),
                    "bottom_right": (bottom_right_lon, bottom_right_lat)
                })
        
        st.session_state.regions = updated_regions
        
        if st.button("➕ 添加区域", key="add_region"):
            st.session_state.regions.append({
                "name": "",
                "top_left": (0.0, 0.0),
                "bottom_right": (0.0, 0.0)
            })
            st.rerun()

        st.markdown("---")
        
        if st.button("执行任务", type="primary", use_container_width=True):
            st.session_state.task_input = task_input
            st.session_state.current_stage = "executing"
            st.session_state.execution_completed = False
            st.session_state.last_result_data = None
            st.rerun()

    elif st.session_state.current_stage == "executing":
        st.subheader("执行任务")

        task_input = st.session_state.task_input
        if task_input:
            if st.session_state.execution_completed:
                col1, col2 = st.columns([3, 1])
                with col2:
                    if st.button("开始新任务", type="primary", key="new_task_cached"):
                        st.session_state.current_plan = None
                        st.session_state.execution_completed = False
                        st.session_state.last_result_data = None
                        st.session_state.current_stage = "input"
                        st.rerun()
                        st.rerun()
                
                st.info("任务已完成，显示结果如下：")
                result_data = st.session_state.get("last_result_data", {})
                work_result = result_data.get("result", {})
                # 优先使用后端返回的updated_plan（包含kg_graph_image_filename）
                plan = work_result.get("updated_plan", st.session_state.current_plan)
                
                if work_result.get("sub_results"):
                    sub_results = work_result.get("sub_results", [])
                    if len(sub_results) > 1:
                        tabs = st.tabs([f"{sub_result.get('unit', f'任务{i+1}')}" for i, sub_result in enumerate(sub_results)])
                        for i, (tab, sub_result) in enumerate(zip(tabs, sub_results)):
                            with tab:
                                _display_result(sub_result, plan)
                    else:
                        if sub_results:
                            _display_result(sub_results[0], plan)
                else:
                    final_result_path = None
                    if work_result.get("final_result_path"):
                        final_result_path = work_result["final_result_path"]
                    elif work_result.get("results"):
                        for r in work_result.get("results", []):
                            if r.get("success") and r.get("result", {}).get("result_path"):
                                final_result_path = r["result"]["result_path"]
                                break

                    if final_result_path:
                        gdf = load_geojson(final_result_path)
                        if gdf is not None:
                            map_reference_points = []
                            
                            st.subheader("结果地图")
                            
                            st.subheader("筛选参数")
                            map_reference_points = []
                            if plan and plan.get("steps"):
                                for step in plan.get("steps", []):
                                    step_params = step.get("params", {})
                                    if step.get("type") == "relative_position" or step.get("tool") == "relative_position_filter_tool":
                                        reference_point = step_params.get("reference_point", {})
                                        reference_direction = step_params.get("reference_direction")
                                        if reference_point:
                                            map_reference_points.append({"point": reference_point, "direction": reference_direction})
                            
                            regions = st.session_state.get("regions", [])
                            if not regions and plan and plan.get("original_query"):
                                regions = parse_regions_from_task(plan.get("original_query"))
                            
                            m = create_map(gdf, reference_points=map_reference_points if map_reference_points else None, regions=regions)
                            if m:
                                st.components.v1.html(m._repr_html_(), height=600)
                            
                            st.subheader("统计信息")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("区域数量", len(gdf))
                            with col2:
                                total_area = gdf['area_m2'].sum() if 'area_m2' in gdf.columns else 0
                                st.metric("总面积 (m²)", f"{total_area:,.0f}")
                            with col3:
                                total_area_km2 = gdf['area_km2'].sum() if 'area_km2' in gdf.columns else 0
                                st.metric("总面积 (km²)", f"{total_area_km2:,.2f}")
                            
                            filter_params_list = format_filter_params(plan.get("steps", []))
                            
                            if filter_params_list:
                                for item in filter_params_list:
                                    st.markdown(f"**步骤 {item['step']} - {item['tool_display_name']}**")
                                    for key, value in item['params'].items():
                                        st.write(f"  • **{key}**: {value}")
                                    if item != filter_params_list[-1]:
                                        st.markdown("---")
                            else:
                                st.info("无筛选参数信息")
                            
                            st.markdown("---")
                            with st.expander("📋 知识抽取问答结果与大模型思考过程", expanded=False):
                                if plan and plan.get("kag_results"):
                                    st.subheader("知识抽取知识召回结果")
                                    kag_results = plan.get("kag_results", [])
                                    st.write(f"共{len(kag_results)}个问题：")
                                    for i, kag_result in enumerate(kag_results, 1):
                                        question = kag_result.get("question", "")
                                        answer = kag_result.get("answer", "")
                                        st.markdown(f"**问题{i}**: {question}")
                                        st.markdown(f"**答案{i}**: {answer}")
                                        st.markdown("---")
                                
                                if plan and plan.get("first_llm_response"):
                                    st.subheader("第一轮大模型思考（工具选择和参数提取）")
                                    first_response = plan.get("first_llm_response", "")
                                    MAX_RESPONSE_LENGTH = 50000
                                    if len(first_response) > MAX_RESPONSE_LENGTH:
                                        st.warning(f"⚠️ 大模型响应较长（{len(first_response)}字符），仅显示前{MAX_RESPONSE_LENGTH}字符")
                                        first_response = first_response[:MAX_RESPONSE_LENGTH] + "\n\n...（内容已截断）"
                                    st.text_area(
                                        "第一轮大模型响应",
                                        value=first_response,
                                        height=200,
                                        key="first_llm_response_display_cached",
                                        label_visibility="collapsed"
                                    )
                                
                                if plan and plan.get("second_llm_response"):
                                    st.subheader("第二轮大模型思考（工具调用计划编织）")
                                    second_response = plan.get("second_llm_response", "")
                                    if len(second_response) > MAX_RESPONSE_LENGTH:
                                        st.warning(f"⚠️ 大模型响应较长（{len(second_response)}字符），仅显示前{MAX_RESPONSE_LENGTH}字符")
                                        second_response = second_response[:MAX_RESPONSE_LENGTH] + "\n\n...（内容已截断）"
                                    st.text_area(
                                        "第二轮大模型响应",
                                        value=second_response,
                                        height=200,
                                        key="second_llm_response_display_cached",
                                        label_visibility="collapsed"
                                    )
            else:
                with st.spinner("正在生成计划并执行任务（这可能需要一些时间）..."):
                    try:
                        response = requests.post(
                            f"{api_url}/api/task",
                            json={"task": task_input},
                            timeout=API_TIMEOUT
                        )

                        if response.status_code == 200:
                            result = response.json()

                            if result.get("success"):
                                st.success("任务执行成功！")
                                
                                st.session_state.execution_completed = True
                                result_data = result.get("result", {})
                                st.session_state.last_result_data = result_data
                                work_result = result_data.get("result", {})
                                plan = result_data.get("plan", {})
                                st.session_state.current_plan = plan

                                col1, col2 = st.columns([3, 1])
                                with col2:
                                    if st.button("开始新任务", type="primary", key="new_task_top"):
                                        st.session_state.current_plan = None
                                        st.session_state.execution_completed = False
                                        st.session_state.last_result_data = None
                                        st.session_state.current_stage = "input"
                                        st.rerun()
                                        st.rerun()

                                if work_result.get("sub_results"):
                                    sub_results = work_result.get("sub_results", [])
                                    if len(sub_results) > 1:
                                        tabs = st.tabs([f"{sub_result.get('unit', f'任务{i+1}')}" for i, sub_result in enumerate(sub_results)])
                                        for i, (tab, sub_result) in enumerate(zip(tabs, sub_results)):
                                            with tab:
                                                _display_result(sub_result, plan)
                                    else:
                                        if sub_results:
                                            _display_result(sub_results[0], plan)
                                else:
                                    final_result_path = None
                                    if work_result.get("final_result_path"):
                                        final_result_path = work_result["final_result_path"]
                                    elif work_result.get("results"):
                                        for r in work_result.get("results", []):
                                            if r.get("success") and r.get("result", {}).get("result_path"):
                                                final_result_path = r["result"]["result_path"]
                                                break

                                    if final_result_path:
                                        gdf = load_geojson(final_result_path)
                                        if gdf is not None:
                                            map_reference_points = []
                                            
                                            st.subheader("结果地图")
                                            
                                            st.subheader("筛选参数")
                                            map_reference_points = []
                                            if plan and plan.get("steps"):
                                                for step in plan.get("steps", []):
                                                    step_params = step.get("params", {})
                                                    if step.get("type") == "relative_position" or step.get("tool") == "relative_position_filter_tool":
                                                        reference_point = step_params.get("reference_point", {})
                                                        reference_direction = step_params.get("reference_direction")
                                                        if reference_point:
                                                            map_reference_points.append({"point": reference_point, "direction": reference_direction})
                                            
                                            regions = st.session_state.get("regions", [])
                                            if not regions and plan and plan.get("original_query"):
                                                regions = parse_regions_from_task(plan.get("original_query"))
                                            
                                            m = create_map(gdf, reference_points=map_reference_points if map_reference_points else None, regions=regions)
                                            if m:
                                                st.components.v1.html(m._repr_html_(), height=600)
                                            
                                            st.subheader("统计信息")
                                            col1, col2, col3 = st.columns(3)
                                            with col1:
                                                st.metric("区域数量", len(gdf))
                                            with col2:
                                                total_area = gdf['area_m2'].sum() if 'area_m2' in gdf.columns else 0
                                                st.metric("总面积 (m²)", f"{total_area:,.0f}")
                                            with col3:
                                                total_area_km2 = gdf['area_km2'].sum() if 'area_km2' in gdf.columns else 0
                                                st.metric("总面积 (km²)", f"{total_area_km2:,.2f}")
                                            
                                            filter_params_list = format_filter_params(plan.get("steps", []))
                                            
                                            if filter_params_list:
                                                for item in filter_params_list:
                                                    st.markdown(f"**步骤 {item['step']} - {item['tool_display_name']}**")
                                                    for key, value in item['params'].items():
                                                        st.write(f"  • **{key}**: {value}")
                                                    if item != filter_params_list[-1]:
                                                        st.markdown("---")
                                            else:
                                                st.info("无筛选参数信息")
                                            
                                            st.markdown("---")
                                            with st.expander("📋 知识抽取问答结果与大模型思考过程", expanded=False):
                                                if plan and plan.get("kag_results"):
                                                    st.subheader("知识抽取知识召回结果")
                                                    kag_results = plan.get("kag_results", [])
                                                    st.write(f"共{len(kag_results)}个问题：")
                                                    for i, kag_result in enumerate(kag_results, 1):
                                                        question = kag_result.get("question", "")
                                                        answer = kag_result.get("answer", "")
                                                        st.markdown(f"**问题{i}**: {question}")
                                                        st.markdown(f"**答案{i}**: {answer}")
                                                        st.markdown("---")
                                                
                                                if plan and plan.get("first_llm_response"):
                                                    st.subheader("第一轮大模型思考（工具选择和参数提取）")
                                                    first_response = plan.get("first_llm_response", "")
                                                    MAX_RESPONSE_LENGTH = 50000
                                                    if len(first_response) > MAX_RESPONSE_LENGTH:
                                                        st.warning(f"⚠️ 大模型响应较长（{len(first_response)}字符），仅显示前{MAX_RESPONSE_LENGTH}字符")
                                                        first_response = first_response[:MAX_RESPONSE_LENGTH] + "\n\n...（内容已截断）"
                                                    st.text_area(
                                                        "第一轮大模型响应",
                                                        value=first_response,
                                                        height=200,
                                                        key="first_llm_response_display",
                                                        label_visibility="collapsed"
                                                    )
                                                
                                                if plan and plan.get("second_llm_response"):
                                                    st.subheader("第二轮大模型思考（工具调用计划编织）")
                                                    second_response = plan.get("second_llm_response", "")
                                                    if len(second_response) > MAX_RESPONSE_LENGTH:
                                                        st.warning(f"⚠️ 大模型响应较长（{len(second_response)}字符），仅显示前{MAX_RESPONSE_LENGTH}字符")
                                                        second_response = second_response[:MAX_RESPONSE_LENGTH] + "\n\n...（内容已截断）"
                                                    st.text_area(
                                                        "第二轮大模型响应",
                                                        value=second_response,
                                                        height=200,
                                                        key="second_llm_response_display",
                                                        label_visibility="collapsed"
                                                    )
                                            
                                            st.markdown("---")
                                            
                                            kg_graph_image_filename = plan.get("kg_graph_image_filename")
                                            retrieved_entities = plan.get("retrieved_entities", [])
                                            retrieved_relations = plan.get("retrieved_relations", [])
                                            
                                            if kg_graph_image_filename:
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
                                                st.subheader("实体关系图")
                                                from frontend_entity_relation_graph import display_kag_entities_relations
                                                display_kag_entities_relations(retrieved_entities, retrieved_relations, show_title=True)
                                            else:
                                                st.info("无实体关系图数据")
                            else:
                                st.error(f"任务执行失败: {result.get('result', {}).get('error', '未知错误')}")
                                if st.button("重新输入任务", type="primary"):
                                    st.session_state.current_plan = None
                                    st.session_state.current_stage = "input"
                                    st.rerun()
                        else:
                            st.error(f"API请求失败: {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"连接API失败: {e}")
                        st.info("请确保后端服务已启动（运行 main.py）")
