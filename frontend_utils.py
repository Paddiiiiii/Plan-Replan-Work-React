import streamlit as st
import geopandas as gpd
import folium
from folium import plugins
from pathlib import Path
from typing import Optional, Dict, List
import re
import socket
from config import GEO_BOUNDS

BASE_DIR = Path(__file__).parent
RESULT_DIR = BASE_DIR / "result"

def get_server_ip():
    """获取本机局域网IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

def load_geojson(file_path: str):
    """加载GeoJSON文件"""
    try:
        gdf = gpd.read_file(file_path)
        return gdf
    except Exception as e:
        st.error(f"加载GeoJSON失败: {e}")
        return None

def parse_regions_from_task(task_text: str) -> List[Dict]:
    """
    从任务文本中解析区域信息（前沿区域、调整线S、调整线P、后方保障区）
    
    格式示例：
    前沿区域：左上角: (118.5, 31.5)右下角: (118.552, 31.545)
    调整线S：左上角: (118.5, 31.518)右下角: (118.552, 31.563)
    调整线P：左上角: (118.5, 31.536)右下角: (118.552, 31.581)
    后方保障区：左上角: (118.552, 31.581)右下角: (118.604, 31.626)
    
    Returns:
        List[Dict]: 区域信息列表，每个元素包含 name, top_left, bottom_right
    """
    regions = []
    
    pattern = r'([^：:]+)[：:]\s*左上角[：:]\s*\(([\d.]+),\s*([\d.]+)\)\s*右下角[：:]\s*\(([\d.]+),\s*([\d.]+)\)'
    
    matches = re.finditer(pattern, task_text)
    for match in matches:
        region_name = match.group(1).strip()
        top_left_lon = float(match.group(2))
        top_left_lat = float(match.group(3))
        bottom_right_lon = float(match.group(4))
        bottom_right_lat = float(match.group(5))
        
        regions.append({
            "name": region_name,
            "top_left": (top_left_lon, top_left_lat),
            "bottom_right": (bottom_right_lon, bottom_right_lat)
        })
    
    return regions

def format_filter_params(steps: List[Dict]) -> List[Dict]:
    """
    格式化筛选参数，用于友好显示
    
    Args:
        steps: 工具执行的步骤列表（可以是plan中的步骤或执行结果中的步骤）
        
    Returns:
        格式化后的筛选参数列表
    """
    formatted_params_list = []
    
    for step_result in steps:
        # 兼容两种格式：plan中的步骤和执行结果中的步骤
        # plan中的步骤没有success字段，执行结果中的步骤有success字段
        if "success" in step_result and not step_result.get("success"):
            continue
        
        # 获取工具名称：优先使用tool字段，如果没有则使用type字段映射
        tool_name = step_result.get("tool", "")
        step_type = step_result.get("type", "")
        
        # 如果没有tool字段但有type字段，进行映射
        if not tool_name and step_type:
            type_to_tool = {
                "buffer": "buffer_filter_tool",
                "elevation": "elevation_filter_tool",
                "slope": "slope_filter_tool",
                "vegetation": "vegetation_filter_tool",
                "relative_position": "relative_position_filter_tool",
                "distance": "distance_filter_tool",
                "area": "area_filter_tool"
            }
            tool_name = type_to_tool.get(step_type, "")
        
        step_params = step_result.get("params", {})
        step_id = step_result.get("step_id", step_result.get("step", ""))
        
        tool_name_map = {
            "buffer_filter_tool": "缓冲区筛选",
            "elevation_filter_tool": "高程筛选",
            "slope_filter_tool": "坡度筛选",
            "vegetation_filter_tool": "植被筛选",
            "distance_filter_tool": "距离筛选",
            "area_filter_tool": "面积筛选",
            "relative_position_filter_tool": "相对位置筛选"
        }
        
        tool_display_name = tool_name_map.get(tool_name, tool_name)
        formatted_params = {
            "step": step_id,
            "tool": tool_name,
            "tool_display_name": tool_display_name,
            "params": {}
        }
        
        if tool_name == "buffer_filter_tool":
            buffer_dist = step_params.get("buffer_distance")
            if buffer_dist is not None:
                formatted_params["params"]["缓冲区距离"] = f"{buffer_dist} 米"
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
                formatted_params["params"]["高程范围"] = elev_str
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
                formatted_params["params"]["坡度范围"] = slope_str
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
                formatted_params["params"]["植被类型"] = ", ".join(veg_list)
            elif exclude_types:
                veg_names = {
                    10: "树", 20: "灌木", 30: "草地", 40: "耕地",
                    50: "建筑", 60: "裸地/稀疏植被", 70: "雪和冰",
                    80: "水体", 90: "湿地", 95: "苔原", 100: "永久性水体"
                }
                exclude_list = [veg_names.get(v, str(v)) for v in exclude_types]
                formatted_params["params"]["排除植被类型"] = ", ".join(exclude_list)
        elif tool_name == "relative_position_filter_tool":
            reference_point = step_params.get("reference_point", {})
            reference_direction = step_params.get("reference_direction")
            position_types = step_params.get("position_types", [])
            if reference_point:
                lon = reference_point.get("lon")
                lat = reference_point.get("lat")
                if lon is not None and lat is not None:
                    formatted_params["params"]["参考点坐标"] = f"({lon:.6f}, {lat:.6f})"
            if reference_direction is not None:
                formatted_params["params"]["参考方向"] = f"{reference_direction}°"
            if position_types:
                formatted_params["params"]["相对位置类型"] = ", ".join(position_types)
        elif tool_name == "distance_filter_tool":
            reference_point = step_params.get("reference_point", {})
            max_distance = step_params.get("max_distance")
            if reference_point:
                lon = reference_point.get("lon")
                lat = reference_point.get("lat")
                if lon is not None and lat is not None:
                    formatted_params["params"]["参考点坐标"] = f"({lon:.6f}, {lat:.6f})"
            if max_distance is not None:
                formatted_params["params"]["最大距离"] = f"{max_distance} 米"
        elif tool_name == "area_filter_tool":
            min_area = step_params.get("min_area")
            max_area = step_params.get("max_area")
            if min_area is not None or max_area is not None:
                area_str = ""
                if min_area is not None:
                    area_str += f"{min_area} km²"
                if max_area is not None:
                    if area_str:
                        area_str += " - "
                    area_str += f"{max_area} km²"
                formatted_params["params"]["面积范围"] = area_str
        
        if formatted_params["params"]:
            formatted_params_list.append(formatted_params)
    
    return formatted_params_list

def create_map(gdf: gpd.GeoDataFrame, reference_point: Optional[Dict] = None, reference_direction: Optional[float] = None, regions: Optional[List[Dict]] = None, reference_points: Optional[List[Dict]] = None) -> Optional[folium.Map]:
    """
    创建地图并显示GeoJSON数据
    
    Args:
        gdf: GeoDataFrame对象
        reference_point: 参考点坐标（兼容旧接口）
        reference_direction: 参考方向（兼容旧接口）
        regions: 区域信息列表
        reference_points: 参考点列表（新接口）
    
    Returns:
        folium.Map对象
    """
    if gdf is None or len(gdf) == 0:
        return None
    
    try:
        bounds = gdf.total_bounds
        center_lat = (bounds[1] + bounds[3]) / 2
        center_lon = (bounds[0] + bounds[2]) / 2
        
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=13,
            tiles="OpenStreetMap"
        )
        
        folium.GeoJson(
            gdf.__geo_interface__,
            style_function=lambda feature: {
                "fillColor": "#3388ff",
                "color": "#0000ff",
                "weight": 2,
                "fillOpacity": 0.5,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[col for col in gdf.columns if col != "geometry"],
                aliases=[col for col in gdf.columns if col != "geometry"],
                localize=True
            )
        ).add_to(m)
        
        if reference_points:
            for ref_info in reference_points:
                ref_point = ref_info.get("point", {})
                ref_dir = ref_info.get("direction")
                if ref_point and ref_dir is not None:
                    lon = ref_point.get("lon")
                    lat = ref_point.get("lat")
                    if lon is not None and lat is not None:
                        folium.Marker(
                            location=[lat, lon],
                            popup=f"参考点 ({lon:.6f}, {lat:.6f})",
                            icon=folium.Icon(color="red", icon="info-sign")
                        ).add_to(m)
                        
                        folium.PolyLine(
                            locations=[
                                [lat, lon],
                                [lat + 0.01 * (ref_dir / 90), lon + 0.01 * (ref_dir / 90)]
                            ],
                            color="red",
                            weight=3,
                            popup=f"参考方向: {ref_dir}°"
                        ).add_to(m)
        elif reference_point and reference_direction is not None:
            lon = reference_point.get("lon")
            lat = reference_point.get("lat")
            if lon is not None and lat is not None:
                folium.Marker(
                    location=[lat, lon],
                    popup=f"参考点 ({lon:.6f}, {lat:.6f})",
                    icon=folium.Icon(color="red", icon="info-sign")
                ).add_to(m)
                
                folium.PolyLine(
                    locations=[
                        [lat, lon],
                        [lat + 0.01 * (reference_direction / 90), lon + 0.01 * (reference_direction / 90)]
                    ],
                    color="red",
                    weight=3,
                    popup=f"参考方向: {reference_direction}°"
                ).add_to(m)
        
        if regions:
            for region in regions:
                region_name = region.get("name", "")
                top_left = region.get("top_left")
                bottom_right = region.get("bottom_right")
                
                if top_left and bottom_right:
                    folium.Rectangle(
                        bounds=[[top_left[1], top_left[0]], [bottom_right[1], bottom_right[0]]],
                        color="green",
                        weight=2,
                        fill=True,
                        fill_color="green",
                        fill_opacity=0.1,
                        popup=region_name
                    ).add_to(m)
                    
                    folium.Marker(
                        location=[top_left[1], top_left[0]],
                        popup=region_name,
                        icon=folium.Icon(color="green", icon="flag")
                    ).add_to(m)
        
        plugins.Fullscreen().add_to(m)
        plugins.MeasureControl().add_to(m)
        
        return m
    except Exception as e:
        st.error(f"创建地图失败: {e}")
        return None
