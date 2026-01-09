from pathlib import Path
from typing import Dict, Any, Optional, List
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
import math
import os
from datetime import datetime
from work.tools.base_tool import BaseTool

BASE_DIR = Path(__file__).parent.parent.parent
RESULT_DIR = BASE_DIR / "result"


class RelativePositionFilterTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="relative_position_filter_tool",
            description="根据参考点和参考方向筛选GeoJSON区域的相对位置（前方、侧翼、后方等）。可以在同一任务中被多次调用，以便根据不同参考单位进行多次筛选"
        )
        self.parameters = {
            "input_geojson_path": {"type": "string", "description": "输入GeoJSON文件路径"},
            "reference_point": {"type": "object", "description": "参考点坐标 {\"lon\": float, \"lat\": float}"},
            "reference_direction": {"type": "number", "description": "参考方向角度（度，0-360，0为正北）"},
            "position_types": {"type": "array", "description": "要筛选的位置类型列表，如 [\"前方\", \"侧翼\", \"后方\"]"},
            "custom_position_config": {"type": "object", "description": "可选，自定义位置配置，格式：{\"位置名\": [{\"min_offset\": -45, \"max_offset\": 45}], ...}，会覆盖默认配置"}
        }
        # 默认相对位置定义
        self.position_config = {
            "最前方": [{"min_offset": -20, "max_offset": 20}],
            "前方": [{"min_offset": -45, "max_offset": 45}],
            "稍偏两侧": [
                {"min_offset": -75, "max_offset": -45},
                {"min_offset": 45, "max_offset": 75}
            ],
            "侧翼": [
                {"min_offset": -135, "max_offset": -45},
                {"min_offset": 45, "max_offset": 135}
            ],
            "两侧": [
                {"min_offset": -135, "max_offset": -45},
                {"min_offset": 45, "max_offset": 135}
            ],
            "两翼": [
                {"min_offset": -135, "max_offset": -45},
                {"min_offset": 45, "max_offset": 135}
            ],
            "偏后": [
                {"min_offset": -180, "max_offset": -120},
                {"min_offset": 120, "max_offset": 180}
            ],
            "后方": [
                {"min_offset": -180, "max_offset": -135},
                {"min_offset": 135, "max_offset": 180}
            ]
        }
    
    def _calculate_bearing(self, ref_lon: float, ref_lat: float, target_lon: float, target_lat: float) -> float:
        """计算从参考点到目标点的方位角（0-360度，0为正北，顺时针）"""
        dx = target_lon - ref_lon
        dy = target_lat - ref_lat
        
        # 地理坐标系统中，需要考虑纬度对经度方向的影响
        avg_lat = (ref_lat + target_lat) / 2
        dx_meters = dx * 111320.0 * math.cos(math.radians(avg_lat))
        dy_meters = dy * 111320.0
        
        # 计算方位角（从正北方向，顺时针）
        bearing = math.degrees(math.atan2(dx_meters, dy_meters)) % 360
        return bearing
    
    def _calculate_angle_diff(self, bearing: float, reference_direction: float) -> float:
        """计算相对于参考方向的角度差（-180到180度）"""
        angle_diff = (bearing - reference_direction + 180) % 360 - 180
        return angle_diff
    
    def _is_position_match(self, angle_diff: float, position_ranges: List[Dict[str, float]]) -> bool:
        """检查角度差是否匹配某个位置类型的配置"""
        for offset_range in position_ranges:
            min_offset = offset_range["min_offset"]
            max_offset = offset_range["max_offset"]
            if min_offset <= angle_diff <= max_offset:
                return True
        return False
    
    def _get_relative_position(self, geometry: Polygon, ref_lon: float, ref_lat: float, 
                               reference_direction: float, position_config: Dict[str, List[Dict[str, float]]]) -> Optional[str]:
        """获取几何图形的相对位置"""
        center = geometry.centroid
        target_lon = center.x
        target_lat = center.y
        
        # 如果参考点和目标点重合，返回None
        if abs(target_lon - ref_lon) < 1e-9 and abs(target_lat - ref_lat) < 1e-9:
            return None
        
        # 计算方位角
        bearing = self._calculate_bearing(ref_lon, ref_lat, target_lon, target_lat)
        
        # 计算相对于参考方向的角度差
        angle_diff = self._calculate_angle_diff(bearing, reference_direction)
        
        # 检查是否匹配某个位置类型
        for position_name, position_ranges in position_config.items():
            if self._is_position_match(angle_diff, position_ranges):
                return position_name
        
        return None
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        input_path = kwargs.get("input_geojson_path")
        reference_point = kwargs.get("reference_point")
        reference_direction = kwargs.get("reference_direction")
        position_types = kwargs.get("position_types")
        custom_position_config = kwargs.get("custom_position_config")
        
        # 参数验证
        if not input_path:
            return {
                "success": False,
                "error": "缺少必需参数: input_geojson_path"
            }
        
        if not reference_point or not isinstance(reference_point, dict):
            return {
                "success": False,
                "error": "缺少必需参数: reference_point，应为 {\"lon\": float, \"lat\": float}"
            }
        
        ref_lon = reference_point.get("lon")
        ref_lat = reference_point.get("lat")
        
        if ref_lon is None or ref_lat is None:
            return {
                "success": False,
                "error": "reference_point 必须包含 lon 和 lat 字段"
            }
        
        if reference_direction is None:
            return {
                "success": False,
                "error": "缺少必需参数: reference_direction"
            }
        
        if not position_types or not isinstance(position_types, list):
            return {
                "success": False,
                "error": "缺少必需参数: position_types，应为数组，如 [\"前方\", \"侧翼\", \"后方\"]"
            }
        
        # 确定使用的位置配置
        if custom_position_config:
            position_config = custom_position_config
        else:
            position_config = self.position_config
        
        # 验证position_types中的位置是否在配置中定义
        for pos_type in position_types:
            if pos_type not in position_config:
                return {
                    "success": False,
                    "error": f"位置类型 '{pos_type}' 未在配置中定义。可用类型: {list(position_config.keys())}"
                }
        
        # 创建筛选后的配置（只包含需要的位置类型）
        filtered_position_config = {pos_type: position_config[pos_type] for pos_type in position_types}
        
        os.makedirs(RESULT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        position_types_str = "_".join(position_types)
        output_path = RESULT_DIR / f"relative_position_filter_{position_types_str}_{timestamp}.geojson"
        
        # 读取输入GeoJSON
        gdf = gpd.read_file(input_path)
        
        if gdf.empty:
            os.makedirs(output_path.parent, exist_ok=True)
            gdf.to_file(output_path, driver='GeoJSON')
            return {
                "success": True,
                "result_path": str(output_path),
                "region_count": 0,
                "total_area_m2": 0.0
            }
        
        valid_indices = []
        relative_positions = []
        
        # 遍历每个区域，判断相对位置
        for idx, row in gdf.iterrows():
            if not isinstance(row.geometry, Polygon):
                continue
            
            position = self._get_relative_position(
                row.geometry, ref_lon, ref_lat, reference_direction, filtered_position_config
            )
            
            if position is not None:
                valid_indices.append(idx)
                relative_positions.append(position)
            else:
                relative_positions.append(None)
        
        # 创建筛选后的GeoDataFrame
        filtered_gdf = gdf.loc[valid_indices].copy()
        
        # 添加相对位置属性
        if relative_positions:
            position_series = pd.Series(relative_positions, index=gdf.index)
            filtered_gdf['relative_position'] = position_series.loc[valid_indices].values
        
        os.makedirs(output_path.parent, exist_ok=True)
        filtered_gdf.to_file(output_path, driver='GeoJSON')
        
        return {
            "success": True,
            "result_path": str(output_path),
            "region_count": len(filtered_gdf),
            "total_area_m2": float(filtered_gdf['area_m2'].sum()) if not filtered_gdf.empty and 'area_m2' in filtered_gdf.columns else 0.0
        }
    
    def validate_params(self, **kwargs) -> bool:
        return (
            kwargs.get("input_geojson_path") is not None and
            kwargs.get("reference_point") is not None and
            kwargs.get("reference_direction") is not None and
            kwargs.get("position_types") is not None
        )

