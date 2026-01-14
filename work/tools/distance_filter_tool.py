from pathlib import Path
from typing import Dict, Any, Optional
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
import math
import os
from datetime import datetime
from work.tools.base_tool import BaseTool

BASE_DIR = Path(__file__).parent.parent.parent
RESULT_DIR = BASE_DIR / "result"


class DistanceFilterTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="distance_filter_tool",
            description="根据离参考点的距离筛选GeoJSON区域，只保留指定距离内的区域"
        )
        self.parameters = {
            "input_geojson_path": {"type": "string", "description": "输入GeoJSON文件路径"},
            "reference_point": {"type": "object", "description": "参考点坐标 {\"lon\": float, \"lat\": float}"},
            "max_distance": {"type": "number", "description": "最大距离（米），只保留距离参考点在此范围内的区域"}
        }
    
    def _calculate_distance(self, ref_lon: float, ref_lat: float, target_lon: float, target_lat: float) -> float:
        """计算从参考点到目标点的距离（米）"""
        # 使用Haversine公式计算两点间的大圆距离
        R = 6371000  # 地球半径（米）
        
        lat1_rad = math.radians(ref_lat)
        lat2_rad = math.radians(target_lat)
        delta_lat = math.radians(target_lat - ref_lat)
        delta_lon = math.radians(target_lon - ref_lon)
        
        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * \
            math.sin(delta_lon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return distance
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        input_path = kwargs.get("input_geojson_path")
        reference_point = kwargs.get("reference_point")
        max_distance = kwargs.get("max_distance")
        
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
        
        if max_distance is None or max_distance <= 0:
            return {
                "success": False,
                "error": "缺少必需参数: max_distance，必须大于0"
            }
        
        os.makedirs(RESULT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = RESULT_DIR / f"distance_filter_{max_distance}m_{timestamp}.geojson"
        
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
        
        # 如果输入区域太大（可能是初始GeoJSON），先进行细分
        # 检查是否有区域面积超过1平方公里
        if 'area_km2' not in gdf.columns:
            # 需要计算面积
            bounds = gdf.total_bounds
            center_lon = (bounds[0] + bounds[2]) / 2
            center_lat = (bounds[1] + bounds[3]) / 2
            utm_zone = int((center_lon + 180) / 6) + 1
            hemisphere = 'north' if center_lat >= 0 else 'south'
            epsg_code = 32600 + utm_zone if hemisphere == 'north' else 32700 + utm_zone
            gdf_utm = gdf.to_crs(f'EPSG:{epsg_code}')
            gdf['area_km2'] = gdf_utm.geometry.area / 1000000
        
        # 如果存在大面积区域（>1平方公里），进行细分
        if gdf['area_km2'].max() > 1.0:
            gdf = self.subdivide_large_regions(gdf, max_area_km2=1.0)
        
        valid_indices = []
        distances_dict = {}  # 使用字典存储，键为索引
        
        # 遍历每个区域，计算距离
        for idx, row in gdf.iterrows():
            if not isinstance(row.geometry, Polygon):
                continue
            
            center = row.geometry.centroid
            target_lon = center.x
            target_lat = center.y
            
            # 计算距离
            distance = self._calculate_distance(ref_lon, ref_lat, target_lon, target_lat)
            
            # 如果距离在范围内，保留
            if distance <= max_distance:
                valid_indices.append(idx)
                distances_dict[idx] = distance
        
        # 创建筛选后的GeoDataFrame
        filtered_gdf = gdf.loc[valid_indices].copy()
        
        # 添加距离属性
        if distances_dict and valid_indices:
            distance_values = [distances_dict.get(idx) for idx in valid_indices]
            filtered_gdf['distance_m'] = distance_values
        
        # 裁剪到地理边界
        filtered_gdf = self.clip_to_bounds(filtered_gdf)
        
        os.makedirs(output_path.parent, exist_ok=True)
        filtered_gdf.to_file(output_path, driver='GeoJSON')
        
        return {
            "success": True,
            "result_path": str(output_path),
            "region_count": len(filtered_gdf),
            "total_area_m2": float(filtered_gdf['area_m2'].sum()) if not filtered_gdf.empty and 'area_m2' in filtered_gdf.columns else 0.0,
            "reference_point": {"lon": ref_lon, "lat": ref_lat},
            "max_distance": max_distance
        }
    
    def validate_params(self, **kwargs) -> bool:
        return (
            kwargs.get("input_geojson_path") is not None and
            kwargs.get("reference_point") is not None and
            kwargs.get("max_distance") is not None and
            kwargs.get("max_distance", 0) > 0
        )

