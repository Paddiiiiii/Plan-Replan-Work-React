"""
GeoJSON文件生成工具
从OSM文件生成初始的全量区域GeoJSON文件
"""
from pathlib import Path
from typing import Optional, Tuple
import geopandas as gpd
from shapely.geometry import Polygon
import os
from datetime import datetime
import xml.etree.ElementTree as ET
import pyproj

BASE_DIR = Path(__file__).parent.parent
OSM_PATH = BASE_DIR / "data" / "nj_merged.osm"
RESULT_DIR = BASE_DIR / "result"


def _get_bounds_from_osm() -> Optional[Tuple[float, float, float, float]]:
    """从OSM文件获取边界"""
    try:
        tree = ET.parse(str(OSM_PATH))
        root = tree.getroot()
        bounds = root.find('bounds')
        if bounds is not None:
            minlat = float(bounds.get('minlat'))
            minlon = float(bounds.get('minlon'))
            maxlat = float(bounds.get('maxlat'))
            maxlon = float(bounds.get('maxlon'))
            return (minlon, minlat, maxlon, maxlat)
    except:
        pass
    return None


def _get_utm_zone(longitude: float) -> int:
    """根据经度获取UTM区号"""
    return int((longitude + 180) / 6) + 1


def _reproject_to_utm(gdf: gpd.GeoDataFrame, crs_code: Optional[str] = None) -> gpd.GeoDataFrame:
    """将GeoDataFrame投影到UTM坐标系"""
    if crs_code:
        target_crs = pyproj.CRS.from_string(crs_code)
    else:
        bounds = gdf.total_bounds
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        utm_zone = _get_utm_zone(center_lon)
        hemisphere = 'north' if center_lat >= 0 else 'south'
        epsg_code = 32600 + utm_zone if hemisphere == 'north' else 32700 + utm_zone
        target_crs = pyproj.CRS.from_epsg(epsg_code)
    
    return gdf.to_crs(target_crs)


def generate_initial_geojson(utm_crs: Optional[str] = None) -> str:
    """
    生成初始的全量区域GeoJSON文件（从OSM边界）
    
    Args:
        utm_crs: 可选的UTM坐标系代码
        
    Returns:
        生成的GeoJSON文件路径
    """
    os.makedirs(RESULT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = RESULT_DIR / f"initial_region_{timestamp}.geojson"
    
    # 从OSM文件获取边界
    bounds = _get_bounds_from_osm()
    if bounds is None:
        # 如果无法从OSM获取边界，使用默认边界（南京区域）
        bounds = (118.5, 31.5, 119.0, 32.5)
    
    # 创建边界多边形
    boundary = Polygon([
        (bounds[0], bounds[1]), (bounds[2], bounds[1]),
        (bounds[2], bounds[3]), (bounds[0], bounds[3]), (bounds[0], bounds[1])
    ])
    
    boundary_gdf = gpd.GeoDataFrame([{'geometry': boundary}], crs='EPSG:4326')
    
    # 投影到UTM坐标系计算面积（使用边界中心点确定UTM区号）
    center_lon = (bounds[0] + bounds[2]) / 2
    center_lat = (bounds[1] + bounds[3]) / 2
    
    if utm_crs is None:
        utm_zone = _get_utm_zone(center_lon)
        hemisphere = 'north' if center_lat >= 0 else 'south'
        epsg_code = 32600 + utm_zone if hemisphere == 'north' else 32700 + utm_zone
        target_utm_crs = pyproj.CRS.from_epsg(epsg_code)
        boundary_gdf_utm = boundary_gdf.to_crs(target_utm_crs)
    else:
        target_utm_crs = pyproj.CRS.from_string(utm_crs)
        boundary_gdf_utm = boundary_gdf.to_crs(target_utm_crs)
    
    # 计算面积并转换回WGS84
    area_m2 = boundary_gdf_utm.geometry.iloc[0].area
    boundary_gdf['area_m2'] = area_m2
    boundary_gdf['area_km2'] = area_m2 / 1000000
    
    # 保存为GeoJSON
    os.makedirs(output_path.parent, exist_ok=True)
    boundary_gdf.to_file(output_path, driver='GeoJSON')
    
    return str(output_path)

