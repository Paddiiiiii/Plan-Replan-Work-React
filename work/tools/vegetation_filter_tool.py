from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
import rasterio
from rasterio.mask import mask
import numpy as np
from pyproj import Transformer
import os
from datetime import datetime
from work.tools.base_tool import BaseTool

from config import PATHS

BASE_DIR = Path(__file__).parent.parent.parent
WORLDCOVER_PATH = BASE_DIR / "data" / "WorldCover_10m_2020_v100_N30E117.tif"
RESULT_DIR = PATHS["result_geojson_dir"]

WORLDCOVER_CLASSES = {
    10: "树",
    20: "灌木",
    30: "草地",
    40: "耕地",
    50: "建筑",
    60: "裸地/稀疏植被",
    70: "雪和冰",
    80: "水体",
    90: "湿地",
    95: "苔原",
    100: "永久性水体"
}

class VegetationFilterTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="vegetation_filter_tool",
            description="根据植被类型筛选GeoJSON区域（基于ESA WorldCover数据）"
        )
        self.parameters = {
            "input_geojson_path": {"type": "string", "description": "输入GeoJSON文件路径"},
            "vegetation_types": {
                "type": "array",
                "description": "植被类型编码列表（可选），支持的值：10(树), 20(灌木), 30(草地), 40(耕地), 50(建筑), 60(裸地/稀疏植被), 70(雪和冰), 80(水体), 90(湿地), 95(苔原), 100(永久性水体)。如果为空，则不过滤植被类型"
            },
            "exclude_types": {
                "type": "array",
                "description": "要排除的植被类型编码列表（可选），与vegetation_types互斥"
            }
        }

    def _get_vegetation_from_worldcover(self, geometry: Polygon, 
                                       vegetation_types: Optional[List[int]] = None,
                                       exclude_types: Optional[List[int]] = None) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        从WorldCover数据中获取区域的植被类型

        返回: (is_valid, vegetation_code, vegetation_name)
        """
        try:
            if not WORLDCOVER_PATH.exists():
                return True, None, None

            with rasterio.open(str(WORLDCOVER_PATH)) as src:
                geometry_transformed = geometry
                if src.crs is not None:
                    try:
                        if src.crs.to_epsg() != 4326:
                            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                            coords = list(geometry.exterior.coords)
                            transformed_coords = [transformer.transform(x, y) for x, y in coords]
                            geometry_transformed = Polygon(transformed_coords)
                    except Exception:
                        geometry_transformed = geometry

                try:
                    out_image, out_transform = mask(src, [geometry_transformed], crop=True, filled=False)
                    veg_data = out_image[0].astype("float64")
                except Exception:
                    # 检查几何图形是否为空
                    if geometry.is_empty:
                        return True, None, None
                    
                    bounds = geometry.bounds
                    center = geometry.centroid
                    
                    # 检查centroid是否为空
                    if center.is_empty:
                        return True, None, None

                    sample_points_ll = [
                        (center.x, center.y),
                        (bounds[0], bounds[1]),
                        (bounds[2], bounds[1]),
                        (bounds[0], bounds[3]),
                        (bounds[2], bounds[3]),
                    ]

                    sample_points = sample_points_ll
                    if src.crs is not None and src.crs.to_epsg() != 4326:
                        try:
                            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                            sample_points = [transformer.transform(x, y) for x, y in sample_points_ll]
                        except Exception:
                            sample_points = sample_points_ll

                    vegetation_codes = []
                    for x, y in sample_points:
                        try:
                            for val in src.sample([(x, y)]):
                                v = int(val[0])
                                if src.nodata is not None and v == int(src.nodata):
                                    continue
                                if np.isfinite(v):
                                    vegetation_codes.append(v)
                        except Exception:
                            continue

                    if not vegetation_codes:
                        return True, None, None

                    unique, counts = np.unique(vegetation_codes, return_counts=True)
                    dominant_code = int(unique[np.argmax(counts)])
                    dominant_name = WORLDCOVER_CLASSES.get(dominant_code, f"未知({dominant_code})")

                    if vegetation_types is not None:
                        if dominant_code not in vegetation_types:
                            return False, dominant_code, dominant_name
                    if exclude_types is not None:
                        if dominant_code in exclude_types:
                            return False, dominant_code, dominant_name

                    return True, dominant_code, dominant_name

                if np.ma.isMaskedArray(veg_data):
                    veg_data = veg_data.filled(np.nan)

                if src.nodata is not None:
                    veg_data[veg_data == float(src.nodata)] = np.nan

                if veg_data.size == 0 or np.all(np.isnan(veg_data)):
                    return True, None, None

                valid_pixels = veg_data[np.isfinite(veg_data)]
                if len(valid_pixels) == 0:
                    return True, None, None

                unique, counts = np.unique(valid_pixels.astype(int), return_counts=True)
                dominant_code = int(unique[np.argmax(counts)])
                dominant_name = WORLDCOVER_CLASSES.get(dominant_code, f"未知({dominant_code})")

                if vegetation_types is not None:
                    type_pixels = np.sum(np.isin(valid_pixels.astype(int), vegetation_types))
                    type_ratio = type_pixels / len(valid_pixels) if len(valid_pixels) > 0 else 0
                    if type_ratio < 0.5:
                        return False, dominant_code, dominant_name

                if exclude_types is not None:
                    exclude_pixels = np.sum(np.isin(valid_pixels.astype(int), exclude_types))
                    exclude_ratio = exclude_pixels / len(valid_pixels) if len(valid_pixels) > 0 else 0
                    if exclude_ratio > 0.5:
                        return False, dominant_code, dominant_name

                return True, dominant_code, dominant_name

        except Exception as e:
            return True, None, None

    def execute(self, **kwargs) -> Dict[str, Any]:
        input_path = kwargs.get("input_geojson_path")
        vegetation_types = kwargs.get("vegetation_types")
        exclude_types = kwargs.get("exclude_types")

        if vegetation_types is not None:
            if isinstance(vegetation_types, (int, float)):
                vegetation_types = [int(vegetation_types)]
            elif isinstance(vegetation_types, list):
                vegetation_types = [int(v) for v in vegetation_types if v is not None]
            else:
                vegetation_types = None

        if exclude_types is not None:
            if isinstance(exclude_types, (int, float)):
                exclude_types = [int(exclude_types)]
            elif isinstance(exclude_types, list):
                exclude_types = [int(v) for v in exclude_types if v is not None]
            else:
                exclude_types = None

        os.makedirs(RESULT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if vegetation_types:
            veg_str = "_".join([str(v) for v in sorted(vegetation_types)])
            output_path = RESULT_DIR / f"vegetation_filter_{veg_str}_{timestamp}.geojson"
        elif exclude_types:
            exclude_str = "_".join([f"ex{str(v)}" for v in sorted(exclude_types)])
            output_path = RESULT_DIR / f"vegetation_filter_{exclude_str}_{timestamp}.geojson"
        else:
            output_path = RESULT_DIR / f"vegetation_filter_all_{timestamp}.geojson"

        if not input_path:
            return {
                "success": False,
                "error": "缺少必需参数 input_geojson_path"
            }

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
            gdf = self.subdivide_large_regions(gdf, max_area_km2=0.0081)

        if vegetation_types is None and exclude_types is None:
            os.makedirs(output_path.parent, exist_ok=True)
            gdf.to_file(output_path, driver='GeoJSON')
            return {
                "success": True,
                "result_path": str(output_path),
                "region_count": len(gdf),
                "total_area_m2": float(gdf['area_m2'].sum()) if not gdf.empty and 'area_m2' in gdf.columns else 0.0
            }

        valid_indices = []
        vegetation_codes = []
        vegetation_names = []

        for idx, row in gdf.iterrows():
            is_valid, veg_code, veg_name = self._get_vegetation_from_worldcover(
                row.geometry, 
                vegetation_types, 
                exclude_types
            )
            if is_valid:
                valid_indices.append(idx)
                vegetation_codes.append(veg_code)
                vegetation_names.append(veg_name)
            else:
                vegetation_codes.append(veg_code)
                vegetation_names.append(veg_name)

        filtered_gdf = gdf.loc[valid_indices].copy()

        if vegetation_codes:
            veg_code_series = pd.Series(vegetation_codes, index=gdf.index)
            veg_name_series = pd.Series(vegetation_names, index=gdf.index)
            filtered_gdf['vegetation_code'] = veg_code_series.loc[valid_indices].values
            filtered_gdf['vegetation_type'] = veg_name_series.loc[valid_indices].values

        # 裁剪到地理边界
        filtered_gdf = self.clip_to_bounds(filtered_gdf)
        
        os.makedirs(output_path.parent, exist_ok=True)
        filtered_gdf.to_file(output_path, driver='GeoJSON')

        return {
            "success": True,
            "result_path": str(output_path),
            "region_count": len(filtered_gdf),
            "total_area_m2": float(filtered_gdf['area_m2'].sum()) if not filtered_gdf.empty and 'area_m2' in filtered_gdf.columns else 0.0
        }

    def validate_params(self, **kwargs) -> bool:
        return kwargs.get("input_geojson_path") is not None
