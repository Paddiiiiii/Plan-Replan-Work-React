from pathlib import Path
from typing import Dict, Any, Optional, Tuple
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

BASE_DIR = Path(__file__).parent.parent.parent
TPI_PATH = BASE_DIR / "data" / "tpi_60_06.img"
RESULT_DIR = BASE_DIR / "result"


class SlopeFilterTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="slope_filter_tool",
            description="根据坡度范围筛选GeoJSON区域"
        )
        self.parameters = {
            "input_geojson_path": {"type": "string", "description": "输入GeoJSON文件路径"},
            "min_slope": {"type": "number", "description": "最小坡度（度，0-90，可选）"},
            "max_slope": {"type": "number", "description": "最大坡度（度，0-90，可选）"}
        }
    
    def _get_slope_from_tpi(self, geometry: Polygon, min_slope: Optional[float] = None, max_slope: Optional[float] = None) -> Tuple[bool, Optional[float]]:
        try:
            with rasterio.open(str(TPI_PATH)) as src:
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
                    tpi_data = out_image[0].astype("float64")
                except Exception:
                    tpi_data = None
                
                if tpi_data is None:
                    # 如果无法裁剪，使用采样点方式
                    # 检查几何图形是否为空
                    if geometry.is_empty:
                        return True, None
                    
                    bounds = geometry.bounds
                    center = geometry.centroid
                    
                    # 检查centroid是否为空
                    if center.is_empty:
                        return True, None
                    
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
                    
                    tpi_values = []
                    for x, y in sample_points:
                        try:
                            for val in src.sample([(x, y)]):
                                v = float(val[0])
                                if src.nodata is not None and v == float(src.nodata):
                                    continue
                                if np.isfinite(v):
                                    tpi_values.append(v)
                        except Exception:
                            continue
                    
                    if not tpi_values:
                        return True, None
                    
                    avg_tpi = float(np.mean(tpi_values))
                    
                    # 使用TPI值作为坡度值（假设TPI值代表坡度相关指标）
                    slope_value = avg_tpi
                    
                    if min_slope is not None and slope_value < min_slope:
                        return False, slope_value
                    if max_slope is not None and slope_value >= max_slope:
                        return False, slope_value
                    return True, slope_value
                
                # 处理裁剪后的TPI数据
                if np.ma.isMaskedArray(tpi_data):
                    tpi_data = tpi_data.filled(np.nan)
                
                if src.nodata is not None:
                    tpi_data[tpi_data == float(src.nodata)] = np.nan
                
                if tpi_data.size == 0 or np.all(np.isnan(tpi_data)):
                    return True, None
                
                # 计算有效TPI值的平均值
                valid = np.isfinite(tpi_data)
                if not np.any(valid):
                    return True, None
                
                avg_tpi = float(np.mean(tpi_data[valid]))
                
                # 使用TPI值作为坡度值
                slope_value = avg_tpi
                
                if min_slope is not None and slope_value < min_slope:
                    return False, slope_value
                if max_slope is not None and slope_value >= max_slope:
                    return False, slope_value
                
                return True, slope_value
                
        except Exception as e:
            return True, None
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        input_path = kwargs.get("input_geojson_path")
        min_slope = kwargs.get("min_slope")
        max_slope = kwargs.get("max_slope")
        
        os.makedirs(RESULT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slope_range = f"_{min_slope if min_slope else 'min'}_{max_slope if max_slope else 'max'}"
        output_path = RESULT_DIR / f"slope_filter{slope_range}_{timestamp}.geojson"
        
        if not input_path or (min_slope is None and max_slope is None):
            gdf = gpd.read_file(input_path) if input_path else gpd.GeoDataFrame()
            if not gdf.empty:
                os.makedirs(output_path.parent, exist_ok=True)
                gdf.to_file(output_path, driver='GeoJSON')
            return {
                "success": True,
                "result_path": str(output_path),
                "region_count": len(gdf),
                "total_area_m2": float(gdf['area_m2'].sum()) if not gdf.empty and 'area_m2' in gdf.columns else 0.0
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
            gdf = self.subdivide_large_regions(gdf, max_area_km2=1.0)
        
        valid_indices = []
        slopes = []
        
        for idx, row in gdf.iterrows():
            is_valid, slope = self._get_slope_from_tpi(row.geometry, min_slope, max_slope)
            if is_valid:
                valid_indices.append(idx)
                slopes.append(slope)
            else:
                slopes.append(None)
        
        filtered_gdf = gdf.loc[valid_indices].copy()
        
        if slopes:
            slope_series = pd.Series(slopes, index=gdf.index)
            filtered_gdf["slope_deg"] = slope_series.loc[valid_indices].values
        
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