from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
import rasterio
import numpy as np
import os
from datetime import datetime
from work.tools.base_tool import BaseTool

BASE_DIR = Path(__file__).parent.parent.parent
DEM_PATH = BASE_DIR / "data" / "ASTGTMV003_N31E118_dem.tif"
RESULT_DIR = BASE_DIR / "result"


class ElevationFilterTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="elevation_filter_tool",
            description="根据高程范围筛选GeoJSON区域"
        )
        self.parameters = {
            "input_geojson_path": {"type": "string", "description": "输入GeoJSON文件路径"},
            "min_elev": {"type": "number", "description": "最小高程（米，可选）"},
            "max_elev": {"type": "number", "description": "最大高程（米，可选）"}
        }
    
    def _get_elevation_from_dem(self, geometry: Polygon, min_elev: Optional[float] = None, max_elev: Optional[float] = None) -> Tuple[bool, Optional[float]]:
        try:
            # 检查几何图形是否为空
            if geometry.is_empty:
                return True, None
            
            with rasterio.open(str(DEM_PATH)) as src:
                bounds = geometry.bounds
                center = geometry.centroid
                
                # 检查centroid是否为空
                if center.is_empty:
                    return True, None
                
                sample_points = [
                    (center.x, center.y),
                    (bounds[0], bounds[1]),
                    (bounds[2], bounds[1]),
                    (bounds[0], bounds[3]),
                    (bounds[2], bounds[3]),
                ]
                
                elevations = []
                for lon, lat in sample_points:
                    try:
                        for val in src.sample([(lon, lat)]):
                            if val[0] is not None and not np.isnan(val[0]):
                                elevations.append(float(val[0]))
                    except:
                        continue
                
                if not elevations:
                    return True, None
                
                avg_elevation = np.mean(elevations)
                min_elevation = np.min(elevations)
                max_elevation = np.max(elevations)
                
                if min_elev is not None and max_elevation < min_elev:
                    return False, avg_elevation
                if max_elev is not None and min_elevation > max_elev:
                    return False, avg_elevation
                
                return True, avg_elevation
                
        except Exception as e:
            return True, None
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        input_path = kwargs.get("input_geojson_path")
        min_elev = kwargs.get("min_elev")
        max_elev = kwargs.get("max_elev")
        
        os.makedirs(RESULT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        elev_range = f"_{min_elev if min_elev else 'min'}_{max_elev if max_elev else 'max'}"
        output_path = RESULT_DIR / f"elevation_filter{elev_range}_{timestamp}.geojson"
        
        if not input_path or (min_elev is None and max_elev is None):
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
        elevations = []
        
        for idx, row in gdf.iterrows():
            is_valid, elevation = self._get_elevation_from_dem(row.geometry, min_elev, max_elev)
            if is_valid:
                valid_indices.append(idx)
                elevations.append(elevation)
            else:
                elevations.append(None)
        
        filtered_gdf = gdf.loc[valid_indices].copy()
        
        if elevations:
            elevation_series = pd.Series(elevations, index=gdf.index)
            filtered_gdf['elevation'] = elevation_series.loc[valid_indices].values
        
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