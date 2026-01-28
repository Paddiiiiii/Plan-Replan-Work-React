from pathlib import Path
from typing import Dict, Any, Optional
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import os
from datetime import datetime
from work.tools.base_tool import BaseTool
from config import PATHS

RESULT_DIR = PATHS["result_geojson_dir"]


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
        gdf_utm['area_km2'] = areas_km2
        
        # 先筛选出面积大于等于min_area_km2的区域（这些区域直接保留）
        large_regions = gdf_utm[areas_km2 >= min_area_km2].copy()
        
        # 对于面积小于min_area_km2的区域，需要合并相邻的区域
        small_regions = gdf_utm[areas_km2 < min_area_km2].copy()
        
        merged_regions = []
        
        if not small_regions.empty:
            # 使用unary_union合并所有相邻的小区域
            # 这会自动将相邻的多边形合并成连续的区域
            merged_geometry = unary_union(small_regions.geometry.tolist())
            
            # 处理合并后的几何图形（可能是MultiPolygon）
            if isinstance(merged_geometry, MultiPolygon):
                # 如果是MultiPolygon，分别处理每个子多边形
                for geom in merged_geometry.geoms:
                    if isinstance(geom, Polygon) and not geom.is_empty:
                        area_km2 = geom.area / 1000000
                        # 只保留合并后面积大于等于min_area_km2的区域
                        if area_km2 >= min_area_km2:
                            merged_regions.append({
                                'geometry': geom,
                                'area_km2': area_km2,
                                'area_m2': geom.area
                            })
            elif isinstance(merged_geometry, Polygon) and not merged_geometry.is_empty:
                # 如果是单个Polygon
                area_km2 = merged_geometry.area / 1000000
                if area_km2 >= min_area_km2:
                    merged_regions.append({
                        'geometry': merged_geometry,
                        'area_km2': area_km2,
                        'area_m2': merged_geometry.area
                    })
        
        # 合并大区域和合并后的小区域
        all_regions = []
        
        # 添加大区域（保留原始属性）
        if not large_regions.empty:
            for idx, row in large_regions.iterrows():
                all_regions.append({
                    'geometry': row.geometry,
                    'area_km2': row['area_km2'],
                    'area_m2': row.geometry.area
                })
        
        # 添加合并后的小区域
        all_regions.extend(merged_regions)
        
        # 创建最终的GeoDataFrame
        if all_regions:
            filtered_gdf_utm = gpd.GeoDataFrame(all_regions, crs=gdf_utm.crs)
        else:
            # 没有符合条件的区域
            filtered_gdf_utm = gpd.GeoDataFrame([], crs=gdf_utm.crs)
        
        # 转换回WGS84
        if not filtered_gdf_utm.empty:
            filtered_gdf = filtered_gdf_utm.to_crs('EPSG:4326')
        else:
            filtered_gdf = gpd.GeoDataFrame([], crs='EPSG:4326')
        
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

