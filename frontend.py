import streamlit as st
import geopandas as gpd
import folium
from folium import plugins
from pathlib import Path
import json
import time
import requests
from typing import Optional
import os

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

BASE_DIR = Path(__file__).parent
RESULT_DIR = BASE_DIR / "result"

try:
    st.set_page_config(
        page_title="空地智能体系统",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

API_URL = "http://localhost:8000"
# 前端调用后端API的超时时间（秒），应大于LLM请求的超时时间
API_TIMEOUT = 240  # 比config.py中的LLM timeout(180)稍长一些

def load_geojson(file_path: str):
    try:
        gdf = gpd.read_file(file_path)
        return gdf
    except Exception as e:
        st.error(f"加载GeoJSON失败: {e}")
        return None

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
    st.title("🤖 空地智能体系统")
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs(["智能体任务", "历史结果", "数据库管理", "API接口"])
    
    with tab1:
        st.header("智能体任务流程")
        
        if "current_plan" not in st.session_state:
            st.session_state.current_plan = None
        if "current_stage" not in st.session_state:
            st.session_state.current_stage = "input"
        if "task_input" not in st.session_state:
            st.session_state.task_input = "计算距离建筑和道路500米以上的空地，高程在100-500米之间"
        
        if st.session_state.current_stage == "input":
            st.subheader("步骤1: 输入任务")
            task_input = st.text_area(
                "输入任务描述",
                value=st.session_state.task_input,
                height=100,
                key="task_input_area"
            )
            
            if st.button("生成计划", type="primary"):
                st.session_state.task_input = task_input
                with st.spinner("正在生成计划..."):
                    try:
                        response = requests.post(
                            f"{API_URL}/api/plan",
                            json={"task": task_input},
                            timeout=API_TIMEOUT
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            if result.get("success"):
                                st.session_state.current_plan = result.get("result", {}).get("plan")
                                st.session_state.current_stage = "plan_review"
                                st.rerun()
                            else:
                                st.error("生成计划失败")
                        else:
                            st.error(f"API请求失败: {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"连接API失败: {e}")
        
        elif st.session_state.current_stage == "plan_review":
            st.subheader("步骤2: 审查计划")
            st.info("请审查以下计划，如有需要可以提出修改意见")
            
            plan = st.session_state.current_plan
            if plan:
                with st.expander("查看计划详情", expanded=True):
                    st.json(plan)
                
                st.markdown("### 计划摘要")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**任务目标**: {plan.get('goal', 'N/A')}")
                    st.write(f"**预计步骤数**: {plan.get('estimated_steps', len(plan.get('steps', [])))}")
                with col2:
                    steps = plan.get('steps', [])
                    st.write(f"**步骤列表**:")
                    for i, step in enumerate(steps, 1):
                        st.write(f"{i}. {step.get('description', step.get('type', 'N/A'))}")
                
                st.markdown("---")
                st.subheader("提出修改意见（可选）")
                feedback = st.text_area(
                    "输入您的修改意见（如果满意可直接点击'确认执行'）",
                    height=100,
                    placeholder="例如：缓冲区距离改为600米，或者添加坡度筛选..."
                )
                
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    if st.button("确认执行", type="primary"):
                        st.session_state.current_stage = "executing"
                        st.rerun()
                with col2:
                    if st.button("重新输入任务"):
                        st.session_state.current_plan = None
                        st.session_state.current_stage = "input"
                        st.rerun()
                with col3:
                    if feedback.strip() and st.button("提交修改意见"):
                        with st.spinner("正在根据您的意见重新规划..."):
                            try:
                                response = requests.post(
                                    f"{API_URL}/api/replan",
                                    json={"plan": plan, "feedback": feedback},
                                    timeout=API_TIMEOUT
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    if result.get("success"):
                                        new_plan = result.get("result", {}).get("plan")
                                        if new_plan:
                                            st.session_state.current_plan = new_plan
                                            st.success("计划已更新，请审查新计划")
                                            st.rerun()
                                        else:
                                            st.error("重新规划返回的计划为空")
                                    else:
                                        st.error(f"重新规划失败: {result.get('message', '未知错误')}")
                                else:
                                    try:
                                        error_detail = response.json()
                                        error_msg = error_detail.get("detail", f"HTTP {response.status_code}")
                                    except:
                                        error_msg = response.text[:500] if response.text else f"HTTP {response.status_code}"
                                    
                                    st.error(f"API请求失败: {error_msg}")
                                    with st.expander("查看详细错误信息"):
                                        st.text(response.text if response.text else "无详细信息")
                            except requests.exceptions.RequestException as e:
                                st.error(f"连接API失败: {e}")
                                st.info("请确保后端服务已启动（运行 main.py）")
        
        elif st.session_state.current_stage == "executing":
            st.subheader("步骤3: 执行计划")
            
            plan = st.session_state.current_plan
            if plan:
                with st.spinner("智能体正在执行计划..."):
                    try:
                        response = requests.post(
                            f"{API_URL}/api/execute",
                            json={"plan": plan},
                            timeout=300
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            
                            if result.get("success"):
                                st.success("任务执行成功！")
                                
                                result_data = result.get("result", {})
                                work_result = result_data.get("result", {})
                                
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
                                
                                st.markdown("---")
                                if st.button("开始新任务"):
                                    st.session_state.current_plan = None
                                    st.session_state.current_stage = "input"
                                    st.rerun()
                            else:
                                st.error(f"任务执行失败: {result.get('result', {}).get('error', '未知错误')}")
                                if st.button("返回修改计划"):
                                    st.session_state.current_stage = "plan_review"
                                    st.rerun()
                        else:
                            st.error(f"API请求失败: {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"连接API失败: {e}")
                        st.info("请确保后端服务已启动（运行 main.py）")
    
    with tab2:
        st.header("历史结果")
        
        if RESULT_DIR.exists():
            result_files = list(RESULT_DIR.glob("*.geojson"))
            result_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            if result_files:
                selected_file = st.selectbox(
                    "选择结果文件",
                    options=result_files,
                    format_func=lambda x: f"{x.name} ({time.ctime(x.stat().st_mtime)})"
                )
                
                if selected_file:
                    gdf = load_geojson(str(selected_file))
                    
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
                st.info("暂无历史结果文件")
        else:
            st.info("结果目录不存在")
    
    with tab3:
        st.header("数据库管理")
        
        if "selected_collection" not in st.session_state:
            st.session_state.selected_collection = "knowledge"
        if "db_data" not in st.session_state:
            st.session_state.db_data = None
        if "db_refresh_key" not in st.session_state:
            st.session_state.db_refresh_key = 0
        if "tab3_should_load" not in st.session_state:
            st.session_state.tab3_should_load = False
        
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_collection = st.selectbox(
                "选择集合",
                options=["knowledge", "tasks", "executions"],
                index=["knowledge", "tasks", "executions"].index(st.session_state.selected_collection) if st.session_state.selected_collection in ["knowledge", "tasks", "executions"] else 0,
                key="collection_selector"
            )
            if selected_collection != st.session_state.selected_collection:
                st.session_state.selected_collection = selected_collection
                st.session_state.db_data = None
                st.session_state.tab3_should_load = True
                st.rerun()
        
        with col2:
            if st.button("刷新数据", key="refresh_db"):
                st.session_state.db_data = None
                st.session_state.db_refresh_key += 1
                st.session_state.tab3_should_load = True
                st.rerun()
        
        if st.session_state.selected_collection == "knowledge":
            if st.button("批量更新（重新初始化军事单位规则）", type="primary"):
                with st.spinner("正在更新knowledge集合..."):
                    try:
                        response = requests.put(
                            f"{API_URL}/api/knowledge/update",
                            timeout=API_TIMEOUT
                        )
                        if response.status_code == 200:
                            result = response.json()
                            if result.get("success"):
                                st.success(f"✓ 已更新 {result.get('count', 0)} 条记录")
                                st.session_state.db_data = None
                                st.session_state.tab3_should_load = True
                                st.rerun()
                            else:
                                st.error(f"更新失败: {result.get('message', '未知错误')}")
                        else:
                            st.error(f"API请求失败: {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"连接API失败: {e}")
        
        st.markdown("---")

        should_load = (
            st.session_state.tab3_should_load or 
            (st.session_state.db_data is None and not st.session_state.tab3_should_load)
        ) and (st.session_state.db_data is None or st.session_state.db_refresh_key > 0)
        
        if should_load:
            with st.spinner("正在加载数据..."):
                try:
                    response = requests.get(
                        f"{API_URL}/api/knowledge",
                        params={"collection": st.session_state.selected_collection},
                        timeout=30
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            st.session_state.db_data = result
                            st.session_state.db_refresh_key = 0
                            st.session_state.tab3_should_load = False  # 数据加载完成，重置标志
                        else:
                            st.error("获取数据失败")
                    else:
                        st.error(f"API请求失败: {response.status_code}")
                except requests.exceptions.RequestException as e:
                    st.error(f"连接API失败: {e}")
                    st.info("请确保后端服务已启动（运行 main.py）")
        
        if st.session_state.db_data:
            data = st.session_state.db_data
            st.subheader(f"{st.session_state.selected_collection} 集合数据")
            st.write(f"**总记录数**: {data.get('count', 0)}")
            
            if data.get("count", 0) > 0:
                items = data.get("items", [])
                
                search_term = st.text_input("搜索", key="db_search", placeholder="搜索文本内容...")
                
                filtered_items = items
                if search_term:
                    filtered_items = [
                        item for item in items
                        if search_term.lower() in item.get("text", "").lower()
                        or search_term.lower() in item.get("id", "").lower()
                    ]
                    st.write(f"**筛选结果**: {len(filtered_items)} 条")
                
                for idx, item in enumerate(filtered_items):
                    with st.expander(f"记录 {idx + 1}: {item.get('id', 'N/A')}", expanded=False):
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.write("**ID**:", item.get("id", "N/A"))
                            st.write("**文本内容**:")
                            st.text_area(
                                "文本内容",
                                value=item.get("text", ""),
                                height=100,
                                key=f"text_{item.get('id')}",
                                disabled=True,
                                label_visibility="collapsed"
                            )
                            st.write("**元数据**:")
                            st.json(item.get("metadata", {}))
                        with col2:
                            delete_key = f"delete_confirm_{item.get('id')}"
                            if delete_key not in st.session_state:
                                st.session_state[delete_key] = False
                            
                            if not st.session_state[delete_key]:
                                if st.button("删除", key=f"delete_{item.get('id')}", type="secondary"):
                                    st.session_state[delete_key] = True
                                    st.rerun()
                            else:
                                st.warning("确认删除？")
                                col_yes, col_no = st.columns(2)
                                with col_yes:
                                    if st.button("确认", key=f"confirm_{item.get('id')}", type="primary"):
                                        try:
                                            delete_response = requests.delete(
                                                f"{API_URL}/api/knowledge/{item.get('id')}",
                                                params={"collection": st.session_state.selected_collection},
                                                timeout=30
                                            )
                                            if delete_response.status_code == 200:
                                                st.success("删除成功")
                                                st.session_state.db_data = None
                                                st.session_state[delete_key] = False
                                                time.sleep(0.5)
                                                st.rerun()
                                            else:
                                                st.error(f"删除失败: {delete_response.status_code}")
                                                st.session_state[delete_key] = False
                                        except requests.exceptions.RequestException as e:
                                            st.error(f"删除请求失败: {e}")
                                            st.session_state[delete_key] = False
                                with col_no:
                                    if st.button("取消", key=f"cancel_{item.get('id')}"):
                                        st.session_state[delete_key] = False
                                        st.rerun()
            else:
                st.info("该集合暂无数据")
        
        st.markdown("---")
        st.subheader("添加新数据")
        
        with st.form("add_data_form"):
            text_input = st.text_area(
                "文本内容",
                height=150,
                placeholder="输入要添加到数据库的文本内容...",
                key="add_text"
            )
            
            metadata_input = st.text_area(
                "元数据（JSON格式）",
                height=100,
                placeholder='{"unit": "单位名", "type": "deployment_rule"}',
                key="add_metadata"
            )
            
            submitted = st.form_submit_button("添加数据", type="primary")
            
            if submitted:
                if not text_input.strip():
                    st.error("请输入文本内容")
                else:
                    metadata = {}
                    if metadata_input.strip():
                        try:
                            import json
                            metadata = json.loads(metadata_input)
                        except json.JSONDecodeError:
                            st.error("元数据格式错误，请输入有效的JSON格式")
                            st.stop()
                    
                    with st.spinner("正在添加数据..."):
                        try:
                            response = requests.post(
                                f"{API_URL}/api/knowledge",
                                json={
                                    "text": text_input,
                                    "metadata": metadata,
                                    "collection": st.session_state.selected_collection
                                },
                                timeout=30
                            )
                            if response.status_code == 200:
                                result = response.json()
                                if result.get("success"):
                                    st.success(f"✓ 数据已添加，ID: {result.get('id')}")
                                    st.session_state.db_data = None
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error(f"添加失败: {result.get('message', '未知错误')}")
                            else:
                                try:
                                    error_detail = response.json()
                                    error_msg = error_detail.get("detail", f"HTTP {response.status_code}")
                                except:
                                    error_msg = response.text[:500] if response.text else f"HTTP {response.status_code}"
                                st.error(f"API请求失败: {error_msg}")
                        except requests.exceptions.RequestException as e:
                            st.error(f"连接API失败: {e}")
    
    with tab4:
        st.header("API接口文档")
        st.markdown("""
        ### 智能体接口
        
        1. **POST /api/plan** - 生成计划
           - 请求体: `{"task": "任务描述"}`
           - 返回: 计划结果
        
        2. **POST /api/replan** - 根据反馈重新规划
           - 请求体: `{"plan": {...}, "feedback": "修改意见"}`
           - 返回: 新计划
        
        3. **POST /api/execute** - 执行计划
           - 请求体: `{"plan": {...}}`
           - 返回: 执行结果
        
        4. **POST /api/task** - 提交任务（完整流程）
           - 请求体: `{"task": "任务描述"}`
           - 返回: 执行结果
        
        5. **GET /api/tools** - 获取可用工具列表
        
        ### 数据库管理接口
        
        6. **GET /api/collections** - 获取所有集合信息
           - 返回: 所有集合的名称和记录数
        
        7. **GET /api/knowledge** - 获取集合数据
           - 查询参数: `collection` (knowledge/tasks/executions)
           - 返回: 集合中的所有记录
        
        8. **POST /api/knowledge** - 添加数据到集合
           - 请求体: `{"text": "文本内容", "metadata": {...}, "collection": "knowledge"}`
           - 返回: 添加成功信息和新记录ID
        
        9. **DELETE /api/knowledge/{id}** - 删除记录
           - 路径参数: `id` (记录ID)
           - 查询参数: `collection` (集合名称)
           - 返回: 删除成功信息
        
        10. **PUT /api/knowledge/update** - 批量更新knowledge集合
            - 调用 `update_knowledge_base()` 重新初始化军事单位部署规则
            - 返回: 更新记录数
        
        ### API地址
        - 后端服务: http://localhost:8000
        - API文档: http://localhost:8000/docs
        """)

if __name__ == "__main__":
    main()