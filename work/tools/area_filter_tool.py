from pathlib import Path
from typing import Dict, Any, Optional
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
import os
from datetime import datetime
from work.tools.base_tool import BaseTool

BASE_DIR = Path(__file__).parent.parent.parent
RESULT_DIR = BASE_DIR / "result"


class AreaFilterTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="area_filter_tool",
            description="根据区域面积筛选GeoJSON区域，将小于指定面积的区域筛掉"
        )
        self.parameters = {
            "input_geojson_path": {"type": "string", "description": "输入GeoJSON文件路径"},
            "min_area_km2": {"type": "number", "description": "最小面积（平方公里），小于此面积的区域将被筛掉"}
        }
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        input_path = kwargs.get("input_geojson_path")
        min_area_km2 = kwargs.get("min_area_km2")
        
        # 参数验证
        if not input_path:
            return {
                "success": False,
                "error": "缺少必需参数: input_geojson_path"
            }
        
        if min_area_km2 is None or min_area_km2 <= 0:
            return {
                "success": False,
                "error": "缺少必需参数: min_area_km2，必须大于0"
            }
        
        os.makedirs(RESULT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = RESULT_DIR / f"area_filter_{min_area_km2}km2_{timestamp}.geojson"
        
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
        
        # 确保gdf使用WGS84坐标系
        if gdf.crs is None:
            gdf.set_crs('EPSG:4326', inplace=True)
        elif gdf.crs.to_string() != 'EPSG:4326':
            gdf = gdf.to_crs('EPSG:4326')
        
        # 投影到UTM坐标系计算面积
        bounds = gdf.total_bounds
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        utm_zone = int((center_lon + 180) / 6) + 1
        hemisphere = 'north' if center_lat >= 0 else 'south'
        epsg_code = 32600 + utm_zone if hemisphere == 'north' else 32700 + utm_zone
        
        gdf_utm = gdf.to_crs(f'EPSG:{epsg_code}')
        
        # 计算每个区域的面积
        areas_km2 = gdf_utm.geometry.area / 1000000  # 转换为平方公里
        
        # 筛选：只保留面积大于等于min_area_km2的区域
        valid_mask = areas_km2 >= min_area_km2
        filtered_gdf_utm = gdf_utm[valid_mask].copy()
        
        # 转换回WGS84
        filtered_gdf = filtered_gdf_utm.to_crs('EPSG:4326')
        
        # 更新面积字段
        filtered_gdf['area_m2'] = filtered_gdf_utm.geometry.area
        filtered_gdf['area_km2'] = filtered_gdf['area_m2'] / 1000000
        
        # 裁剪到地理边界
        filtered_gdf = self.clip_to_bounds(filtered_gdf)
        
        # 重新计算面积（裁剪后）
        if not filtered_gdf.empty:
            filtered_gdf_utm = filtered_gdf.to_crs(f'EPSG:{epsg_code}')
            filtered_gdf['area_m2'] = filtered_gdf_utm.geometry.area
            filtered_gdf['area_km2'] = filtered_gdf['area_m2'] / 1000000
            filtered_gdf = filtered_gdf.to_crs('EPSG:4326')
        
        os.makedirs(output_path.parent, exist_ok=True)
        filtered_gdf.to_file(output_path, driver='GeoJSON')
        
        return {
            "success": True,
            "result_path": str(output_path),
            "region_count": len(filtered_gdf),
            "total_area_m2": float(filtered_gdf['area_m2'].sum()) if not filtered_gdf.empty and 'area_m2' in filtered_gdf.columns else 0.0,
            "min_area_km2": min_area_km2
        }
    
    def validate_params(self, **kwargs) -> bool:
        return (
            kwargs.get("input_geojson_path") is not None and
            kwargs.get("min_area_km2") is not None and
            kwargs.get("min_area_km2", 0) > 0
        )

