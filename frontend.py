import streamlit as st
import geopandas as gpd
import folium
from folium import plugins
from pathlib import Path
import json
import time
import requests
from typing import Optional, Dict
import os

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

BASE_DIR = Path(__file__).parent
RESULT_DIR = BASE_DIR / "result"

try:
    st.set_page_config(
        page_title="部署智能体",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

API_URL = "http://localhost:8000"
API_TIMEOUT = 1800  # 增加到1800秒（30分钟），支持两轮LLM思考的长时间处理（每轮最长800秒）

def load_geojson(file_path: str):
    try:
        gdf = gpd.read_file(file_path)
        return gdf
    except Exception as e:
        st.error(f"加载GeoJSON失败: {e}")
        return None

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
    m = create_map(gdf)
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
    filter_params = {}
    
    for step_result in steps:
        if step_result.get("success"):
            tool_name = step_result.get("tool", "")
            step_params = step_result.get("params", {})
            
            if tool_name == "buffer_filter_tool":
                buffer_dist = step_params.get("buffer_distance")
                if buffer_dist is not None:
                    filter_params["缓冲区距离"] = f"{buffer_dist} 米"
            elif tool_name == "elevation_filter_tool":
                min_elev = step_params.get("min_elev")
                max_elev = step_params.get("max_elev")
                if min_elev is not None or max_elev is not None:
                    elev_str = ""
                    if min_elev is not None:
                        elev_str += f"{min_elev} 米"
                    if max_elev is not None:
                        if elev_str:
                            elev_str += " - "
                        elev_str += f"{max_elev} 米"
                    filter_params["高程范围"] = elev_str
            elif tool_name == "slope_filter_tool":
                min_slope = step_params.get("min_slope")
                max_slope = step_params.get("max_slope")
                if min_slope is not None or max_slope is not None:
                    slope_str = ""
                    if min_slope is not None:
                        slope_str += f"{min_slope}°"
                    if max_slope is not None:
                        if slope_str:
                            slope_str += " - "
                        slope_str += f"{max_slope}°"
                    filter_params["坡度范围"] = slope_str
            elif tool_name == "vegetation_filter_tool":
                veg_types = step_params.get("vegetation_types", [])
                exclude_types = step_params.get("exclude_types", [])
                if veg_types:
                    veg_names = {
                        10: "树", 20: "灌木", 30: "草地", 40: "耕地",
                        50: "建筑", 60: "裸地/稀疏植被", 70: "雪和冰",
                        80: "水体", 90: "湿地", 95: "苔原", 100: "永久性水体"
                    }
                    veg_list = [veg_names.get(v, str(v)) for v in veg_types]
                    filter_params["植被类型"] = ", ".join(veg_list)
                elif exclude_types:
                    veg_names = {
                        10: "树", 20: "灌木", 30: "草地", 40: "耕地",
                        50: "建筑", 60: "裸地/稀疏植被", 70: "雪和冰",
                        80: "水体", 90: "湿地", 95: "苔原", 100: "永久性水体"
                    }
                    exclude_list = [veg_names.get(v, str(v)) for v in exclude_types]
                    filter_params["排除植被类型"] = ", ".join(exclude_list)
            elif tool_name == "relative_position_filter_tool":
                reference_point = step_params.get("reference_point", {})
                reference_direction = step_params.get("reference_direction")
                position_types = step_params.get("position_types", [])
                if reference_point:
                    lon = reference_point.get("lon")
                    lat = reference_point.get("lat")
                    if lon is not None and lat is not None:
                        filter_params["参考点坐标"] = f"({lon:.6f}, {lat:.6f})"
                if reference_direction is not None:
                    filter_params["参考方向"] = f"{reference_direction}°"
                if position_types:
                    filter_params["相对位置类型"] = ", ".join(position_types)
    
    if filter_params:
        for key, value in filter_params.items():
            st.write(f"**{key}**: {value}")
    else:
        st.info("无筛选参数信息")

def create_map(gdf: gpd.GeoDataFrame) -> Optional[folium.Map]:
    if gdf is None or gdf.empty:
        return None

    try:
        bounds = gdf.total_bounds
        center_lat = (bounds[1] + bounds[3]) / 2
        center_lon = (bounds[0] + bounds[2]) / 2

        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=12,
            tiles='OpenStreetMap'
        )

        geojson_layer = folium.GeoJson(
            gdf.to_json(),
            name='空地区域',
            style_function=lambda feature: {
                'fillColor': '#3388ff',
                'color': '#3388ff',
                'weight': 2,
                'fillOpacity': 0.5,
            }
        )

        if 'area_km2' in gdf.columns or 'area_m2' in gdf.columns:
            geojson_layer.add_child(
                folium.GeoJsonTooltip(
                    fields=['area_km2', 'area_m2'] if 'area_km2' in gdf.columns else ['area_m2'],
                    aliases=['面积 (km²):', '面积 (m²):'] if 'area_km2' in gdf.columns else ['面积 (m²):'],
                )
            )

        geojson_layer.add_to(m)
        folium.LayerControl().add_to(m)

        return m
    except Exception as e:
        st.error(f"创建地图失败: {e}")
        return None

def main():
    st.title("🤖 部署智能体系统")
    
    # 在顶部显示API文档链接
    st.info(
        f"📚 **API文档**: [Swagger UI]({API_URL}/docs) | [ReDoc]({API_URL}/redoc) | "
        f"**API地址**: {API_URL}"
    )
    
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["智能体任务", "历史结果", "实体-关系图"])

    with tab1:
        st.header("智能体任务流程")

        if "current_plan" not in st.session_state:
            st.session_state.current_plan = None
        if "current_stage" not in st.session_state:
            st.session_state.current_stage = "input"
        if "task_input" not in st.session_state:
            st.session_state.task_input = "我方现在正在进攻，步兵部署在118.786310,32.027770位置，战场正方向为110°（正北方向为0°），筛选出坦克的部署位置"

        if st.session_state.current_stage == "input":
            st.subheader("输入任务")
            task_input = st.text_area(
                "输入任务描述",
                value=st.session_state.task_input,
                height=100,
                key="task_input_area"
            )

            if st.button("执行任务", type="primary"):
                st.session_state.task_input = task_input
                st.session_state.current_stage = "executing"
                st.rerun()

        elif st.session_state.current_stage == "executing":
            st.subheader("执行任务")

            task_input = st.session_state.task_input
            if task_input:
                with st.spinner("正在生成计划并执行任务（这可能需要一些时间）..."):
                    try:
                        # 直接调用完整任务接口（规划+执行）
                        response = requests.post(
                            f"{API_URL}/api/task",
                            json={"task": task_input},
                            timeout=API_TIMEOUT
                        )

                        if response.status_code == 200:
                            result = response.json()

                            if result.get("success"):
                                st.success("任务执行成功！")

                                result_data = result.get("result", {})
                                work_result = result_data.get("result", {})
                                plan = result_data.get("plan", {})  # 从结果中获取plan
                                # 保存plan到session_state，供_display_result使用
                                st.session_state.current_plan = plan

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
                                            st.subheader("结果地图")
                                            m = create_map(gdf)
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

                                            # 显示筛选参数
                                            st.subheader("筛选参数")
                                            filter_params = {}
                                            
                                            # 从执行结果中提取筛选参数
                                            if work_result.get("results"):
                                                for step_result in work_result.get("results", []):
                                                    if step_result.get("success"):
                                                        tool_name = step_result.get("tool", "")
                                                        step_params = step_result.get("params", {})
                                                        
                                                        if tool_name == "buffer_filter_tool":
                                                            buffer_dist = step_params.get("buffer_distance")
                                                            if buffer_dist is not None:
                                                                filter_params["缓冲区距离"] = f"{buffer_dist} 米"
                                                        elif tool_name == "elevation_filter_tool":
                                                            min_elev = step_params.get("min_elev")
                                                            max_elev = step_params.get("max_elev")
                                                            if min_elev is not None or max_elev is not None:
                                                                elev_str = ""
                                                                if min_elev is not None:
                                                                    elev_str += f"{min_elev} 米"
                                                                if max_elev is not None:
                                                                    if elev_str:
                                                                        elev_str += " - "
                                                                    elev_str += f"{max_elev} 米"
                                                                filter_params["高程范围"] = elev_str
                                                        elif tool_name == "slope_filter_tool":
                                                            min_slope = step_params.get("min_slope")
                                                            max_slope = step_params.get("max_slope")
                                                            if min_slope is not None or max_slope is not None:
                                                                slope_str = ""
                                                                if min_slope is not None:
                                                                    slope_str += f"{min_slope}°"
                                                                if max_slope is not None:
                                                                    if slope_str:
                                                                        slope_str += " - "
                                                                    slope_str += f"{max_slope}°"
                                                                filter_params["坡度范围"] = slope_str
                                                        elif tool_name == "vegetation_filter_tool":
                                                            veg_types = step_params.get("vegetation_types", [])
                                                            exclude_types = step_params.get("exclude_types", [])
                                                            if veg_types:
                                                                veg_names = {
                                                                    10: "树", 20: "灌木", 30: "草地", 40: "耕地",
                                                                    50: "建筑", 60: "裸地/稀疏植被", 70: "雪和冰",
                                                                    80: "水体", 90: "湿地", 95: "苔原", 100: "永久性水体"
                                                                }
                                                                veg_list = [veg_names.get(v, str(v)) for v in veg_types]
                                                                filter_params["植被类型"] = ", ".join(veg_list)
                                                            elif exclude_types:
                                                                veg_names = {
                                                                    10: "树", 20: "灌木", 30: "草地", 40: "耕地",
                                                                    50: "建筑", 60: "裸地/稀疏植被", 70: "雪和冰",
                                                                    80: "水体", 90: "湿地", 95: "苔原", 100: "永久性水体"
                                                                }
                                                                exclude_list = [veg_names.get(v, str(v)) for v in exclude_types]
                                                                filter_params["排除植被类型"] = ", ".join(exclude_list)
                                                        elif tool_name == "relative_position_filter_tool":
                                                            reference_point = step_params.get("reference_point", {})
                                                            reference_direction = step_params.get("reference_direction")
                                                            position_types = step_params.get("position_types", [])
                                                            if reference_point:
                                                                lon = reference_point.get("lon")
                                                                lat = reference_point.get("lat")
                                                                if lon is not None and lat is not None:
                                                                    filter_params["参考点坐标"] = f"({lon:.6f}, {lat:.6f})"
                                                            if reference_direction is not None:
                                                                filter_params["参考方向"] = f"{reference_direction}°"
                                                            if position_types:
                                                                filter_params["相对位置类型"] = ", ".join(position_types)
                                            
                                            # 如果执行结果中没有参数，尝试从plan中提取
                                            if not filter_params and plan:
                                                if plan.get("steps"):
                                                    for step in plan.get("steps", []):
                                                        step_params = step.get("params", {})
                                                        if step.get("tool") == "buffer_filter_tool":
                                                            if "buffer_distance" in step_params:
                                                                filter_params["缓冲区距离"] = f"{step_params['buffer_distance']} 米"
                                                        elif step.get("tool") == "elevation_filter_tool":
                                                            min_elev = step_params.get("min_elev")
                                                            max_elev = step_params.get("max_elev")
                                                            if min_elev is not None or max_elev is not None:
                                                                elev_str = ""
                                                                if min_elev is not None:
                                                                    elev_str += f"{min_elev} 米"
                                                                if max_elev is not None:
                                                                    if elev_str:
                                                                        elev_str += " - "
                                                                    elev_str += f"{max_elev} 米"
                                                                filter_params["高程范围"] = elev_str
                                                        elif step.get("tool") == "slope_filter_tool":
                                                            min_slope = step_params.get("min_slope")
                                                            max_slope = step_params.get("max_slope")
                                                            if min_slope is not None or max_slope is not None:
                                                                slope_str = ""
                                                                if min_slope is not None:
                                                                    slope_str += f"{min_slope}°"
                                                                if max_slope is not None:
                                                                    if slope_str:
                                                                        slope_str += " - "
                                                                    slope_str += f"{max_slope}°"
                                                                filter_params["坡度范围"] = slope_str
                                                        elif step.get("tool") == "vegetation_filter_tool":
                                                            veg_types = step_params.get("vegetation_types", [])
                                                            exclude_types = step_params.get("exclude_types", [])
                                                            if veg_types:
                                                                veg_names = {
                                                                    10: "树", 20: "灌木", 30: "草地", 40: "耕地",
                                                                    50: "建筑", 60: "裸地/稀疏植被", 70: "雪和冰",
                                                                    80: "水体", 90: "湿地", 95: "苔原", 100: "永久性水体"
                                                                }
                                                                veg_list = [veg_names.get(v, str(v)) for v in veg_types]
                                                                filter_params["植被类型"] = ", ".join(veg_list)
                                                            elif exclude_types:
                                                                veg_names = {
                                                                    10: "树", 20: "灌木", 30: "草地", 40: "耕地",
                                                                    50: "建筑", 60: "裸地/稀疏植被", 70: "雪和冰",
                                                                    80: "水体", 90: "湿地", 95: "苔原", 100: "永久性水体"
                                                                }
                                                                exclude_list = [veg_names.get(v, str(v)) for v in exclude_types]
                                                                filter_params["排除植被类型"] = ", ".join(exclude_list)
                                                        elif step.get("type") == "relative_position" or step.get("tool") == "relative_position_filter_tool":
                                                            reference_point = step_params.get("reference_point", {})
                                                            reference_direction = step_params.get("reference_direction")
                                                            position_types = step_params.get("position_types", [])
                                                            if reference_point:
                                                                lon = reference_point.get("lon")
                                                                lat = reference_point.get("lat")
                                                                if lon is not None and lat is not None:
                                                                    filter_params["参考点坐标"] = f"({lon:.6f}, {lat:.6f})"
                                                            if reference_direction is not None:
                                                                filter_params["参考方向"] = f"{reference_direction}°"
                                                            if position_types:
                                                                filter_params["相对位置类型"] = ", ".join(position_types)
                                            
                                            if filter_params:
                                                param_cols = st.columns(len(filter_params))
                                                for idx, (key, value) in enumerate(filter_params.items()):
                                                    with param_cols[idx]:
                                                        st.metric(key, value)
                                            else:
                                                st.info("无筛选参数信息")

                                st.markdown("---")

                                if st.button("开始新任务", type="primary"):
                                    # 重置状态，直接回到任务输入界面
                                    st.session_state.current_plan = None
                                    st.session_state.current_stage = "input"
                                    st.rerun()
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

    with tab2:
        st.header("历史结果")

        if "results_list" not in st.session_state:
            st.session_state.results_list = None
        if "results_refresh_key" not in st.session_state:
            st.session_state.results_refresh_key = 0

        col1, col2 = st.columns([2, 1])
        with col2:
            if st.button("刷新列表", key="refresh_results"):
                st.session_state.results_list = None
                st.session_state.results_refresh_key += 1
                st.rerun()

        if st.session_state.results_list is None:
            with st.spinner("正在加载结果文件列表..."):
                try:
                    response = requests.get(
                        f"{API_URL}/api/results",
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
                    options=list(result_options.keys())
                )

                if selected_display:
                    selected_filename = result_options[selected_display]

                    with st.spinner("正在加载结果文件..."):
                        try:
                            response = requests.get(
                                f"{API_URL}/api/results/{selected_filename}",
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
                                    st.subheader("地图显示")
                                    m = create_map(gdf)
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
                            else:
                                st.error(f"获取结果文件失败: {response.status_code}")
                        except requests.exceptions.RequestException as e:
                            st.error(f"连接API失败: {e}")
            else:
                st.info("暂无历史结果文件")
        else:
            st.info("正在加载结果文件列表...")

    with tab3:
        st.header("实体-关系图")

        # 初始化session state（只在首次访问时初始化）
        if "kg_data" not in st.session_state:
            st.session_state.kg_data = None
        if "kg_should_load" not in st.session_state:
            st.session_state.kg_should_load = False  # 默认不加载，只有用户点击时才加载
        if "kg_loaded" not in st.session_state:
            st.session_state.kg_loaded = False  # 标记是否已经加载过
        if "selected_entity_types" not in st.session_state:
            st.session_state.selected_entity_types = []
        if "selected_relation_types" not in st.session_state:
            st.session_state.selected_relation_types = []
        if "kg_search_term" not in st.session_state:
            st.session_state.kg_search_term = ""
        if "selected_node" not in st.session_state:
            st.session_state.selected_node = None

        # 如果还没有加载过数据，显示加载按钮
        if not st.session_state.kg_loaded and st.session_state.kg_data is None:
            st.info("👆 点击下方按钮加载知识图谱数据")
            if st.button("加载知识图谱数据", type="primary", key="load_kg_data"):
                st.session_state.kg_should_load = True
                st.session_state.kg_loaded = True
                st.rerun()

        # 控制栏（只在已加载数据时显示）
        if st.session_state.kg_loaded or st.session_state.kg_data is not None:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                search_term = st.text_input(
                    "搜索实体",
                    value=st.session_state.kg_search_term,
                    placeholder="输入实体名称进行搜索...",
                    key="kg_search_input"
                )
                if search_term != st.session_state.kg_search_term:
                    st.session_state.kg_search_term = search_term
                    st.rerun()
            
            with col2:
                if st.button("刷新数据", key="refresh_kg"):
                    st.session_state.kg_data = None
                    st.session_state.kg_should_load = True
                    st.rerun()
            
            with col3:
                if st.button("重置筛选", key="reset_filters"):
                    st.session_state.selected_entity_types = []
                    st.session_state.selected_relation_types = []
                    st.session_state.kg_search_term = ""
                    st.rerun()

        # 加载数据（只在kg_should_load为True时加载）
        if st.session_state.kg_should_load:
            with st.spinner("正在从checkpoint加载知识图谱数据..."):
                try:
                    response = requests.get(
                        f"{API_URL}/api/kg",
                        timeout=60
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            st.session_state.kg_data = result
                            st.session_state.kg_should_load = False
                            st.success("数据加载成功！")
                            st.rerun()
                        else:
                            st.error("获取知识图谱数据失败")
                            st.session_state.kg_should_load = False
                    else:
                        st.error(f"API请求失败: {response.status_code}")
                        st.session_state.kg_should_load = False
                except requests.exceptions.RequestException as e:
                    st.error(f"连接API失败: {e}")
                    st.info("请确保后端服务已启动（运行 main.py）")
                    st.session_state.kg_should_load = False

        # 显示统计信息
        if st.session_state.kg_data:
            kg_data = st.session_state.kg_data
            entities = kg_data.get("entities", [])
            relations = kg_data.get("relations", [])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("实体总数", kg_data.get("entity_count", len(entities)))
            with col2:
                st.metric("关系总数", kg_data.get("relation_count", len(relations)))
            with col3:
                # 统计实体类型
                entity_types = {}
                for entity in entities:
                    entity_type = entity.get("type", "Unknown")
                    entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
                st.metric("实体类型数", len(entity_types))

            st.markdown("---")

            # 筛选控件
            col1, col2 = st.columns(2)
            with col1:
                # 实体类型筛选
                all_entity_types = sorted(set([e.get("type", "Unknown") for e in entities]))
                selected_entity_types = st.multiselect(
                    "筛选实体类型",
                    options=all_entity_types,
                    default=st.session_state.selected_entity_types,
                    key="entity_type_filter"
                )
                if selected_entity_types != st.session_state.selected_entity_types:
                    st.session_state.selected_entity_types = selected_entity_types
                    st.rerun()
            
            with col2:
                # 关系类型筛选
                all_relation_types = sorted(set([r.get("type", "Unknown") for r in relations]))
                selected_relation_types = st.multiselect(
                    "筛选关系类型",
                    options=all_relation_types,
                    default=st.session_state.selected_relation_types,
                    key="relation_type_filter"
                )
                if selected_relation_types != st.session_state.selected_relation_types:
                    st.session_state.selected_relation_types = selected_relation_types
                    st.rerun()

            # 应用筛选
            filtered_entities = entities
            filtered_relations = relations

            if st.session_state.selected_entity_types:
                filtered_entities = [
                    e for e in entities 
                    if e.get("type", "Unknown") in st.session_state.selected_entity_types
                ]
                # 只显示与筛选实体相关的关系
                entity_ids = set([e.get("id") for e in filtered_entities])
                filtered_relations = [
                    r for r in relations
                    if r.get("source") in entity_ids and r.get("target") in entity_ids
                ]

            if st.session_state.selected_relation_types:
                filtered_relations = [
                    r for r in filtered_relations
                    if r.get("type", "Unknown") in st.session_state.selected_relation_types
                ]
                # 只显示与筛选关系相关的实体
                related_entity_ids = set()
                for r in filtered_relations:
                    related_entity_ids.add(r.get("source"))
                    related_entity_ids.add(r.get("target"))
                filtered_entities = [
                    e for e in filtered_entities
                    if e.get("id") in related_entity_ids
                ]

            if st.session_state.kg_search_term:
                search_lower = st.session_state.kg_search_term.lower()
                filtered_entities = [
                    e for e in filtered_entities
                    if search_lower in e.get("name", "").lower() or search_lower in e.get("id", "").lower()
                ]
                entity_ids = set([e.get("id") for e in filtered_entities])
                filtered_relations = [
                    r for r in filtered_relations
                    if r.get("source") in entity_ids and r.get("target") in entity_ids
                ]

            st.write(f"**显示**: {len(filtered_entities)} 个实体, {len(filtered_relations)} 个关系")

            # 创建可视化
            if filtered_entities or filtered_relations:
                try:
                    from pyvis.network import Network
                    import tempfile

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

                    # 添加节点
                    entity_map = {}
                    for entity in filtered_entities:
                        entity_id = entity.get("id", "")
                        entity_name = entity.get("name", entity_id)
                        entity_type = entity.get("type", "Unknown")
                        color = entity_type_colors.get(entity_type, "#888888")
                        
                        # 构建节点标题（显示详细信息）
                        title = f"<b>{entity_name}</b><br>类型: {entity_type}<br>ID: {entity_id}"
                        properties = entity.get("properties", {})
                        if properties:
                            title += "<br>属性:"
                            for key, value in list(properties.items())[:5]:  # 只显示前5个属性
                                title += f"<br>  {key}: {value}"
                        
                        # 高亮搜索匹配的节点
                        node_color = "#FFD700" if st.session_state.kg_search_term and st.session_state.kg_search_term.lower() in entity_name.lower() else color
                        
                        net.add_node(
                            entity_id,
                            label=entity_name[:20],  # 限制标签长度
                            title=title,
                            color=node_color,
                            size=20
                        )
                        entity_map[entity_id] = entity

                    # 添加边
                    for relation in filtered_relations:
                        source = relation.get("source", "")
                        target = relation.get("target", "")
                        relation_type = relation.get("type", "Unknown")
                        
                        if source in entity_map and target in entity_map:
                            net.add_edge(
                                source,
                                target,
                                label=relation_type[:15],  # 限制标签长度
                                title=relation_type,
                                color="#888888",
                                width=2
                            )

                    # 配置物理引擎
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
                          "iterations": 100
                        }
                      },
                      "interaction": {
                        "hover": true,
                        "tooltipDelay": 200,
                        "zoomView": true,
                        "dragView": true
                      }
                    }
                    """)

                    # 生成HTML到临时文件
                    import tempfile
                    import os
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as html_file:
                        net.save_graph(html_file.name)
                        html_path = html_file.name
                    
                    # 读取HTML内容并显示
                    try:
                        with open(html_path, "r", encoding="utf-8") as f:
                            html_content = f.read()
                        
                        # 在Streamlit中显示
                        st.components.v1.html(html_content, height=650, scrolling=True)
                    finally:
                        # 清理临时文件
                        try:
                            os.unlink(html_path)
                        except:
                            pass

                except ImportError:
                    st.error("pyvis库未安装，请运行: pip install pyvis")
                    st.code("pip install pyvis", language="bash")
                except Exception as e:
                    st.error(f"生成可视化失败: {e}")
                    import traceback
                    st.code(traceback.format_exc())

            else:
                st.info("没有数据可显示。请调整筛选条件或确保checkpoint文件存在。")

            # 节点详情面板
            if st.session_state.selected_node:
                st.markdown("---")
                st.subheader("节点详情")
                node_data = st.session_state.selected_node
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.write("**ID**:", node_data.get("id", "N/A"))
                    st.write("**名称**:", node_data.get("name", "N/A"))
                    st.write("**类型**:", node_data.get("type", "N/A"))
                with col2:
                    st.write("**属性**:")
                    st.json(node_data.get("properties", {}))


if __name__ == "__main__":
    main()