from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple, Optional
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
import pyproj
import os
from datetime import datetime
from work.tools.base_tool import BaseTool

BASE_DIR = Path(__file__).parent.parent.parent
OSM_PATH = BASE_DIR / "data" / "nj_merged.osm"
RESULT_DIR = BASE_DIR / "result"


class BufferFilterTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="buffer_filter_tool",
            description="根据建筑和道路缓冲区筛选GeoJSON区域，排除距离建筑和道路过近的区域"
        )
        self.parameters = {
            "input_geojson_path": {"type": "string", "description": "输入GeoJSON文件路径"},
            "buffer_distance": {"type": "number", "description": "缓冲区距离（米）"},
            "utm_crs": {"type": "string", "description": "UTM坐标系统（可选）"}
        }
    
    def _parse_osm_file(self) -> Tuple[dict, List[dict], List[dict]]:
        nodes = {}
        buildings = []
        roads = []
        
        context = ET.iterparse(str(OSM_PATH), events=('start', 'end'))
        context = iter(context)
        event, root = next(context)
        
        for event, elem in context:
            if event == 'end':
                if elem.tag == 'node':
                    node_id = elem.get('id')
                    lat = float(elem.get('lat'))
                    lon = float(elem.get('lon'))
                    nodes[node_id] = (lon, lat)
                    elem.clear()
                
                elif elem.tag == 'way':
                    way_id = elem.get('id')
                    nd_refs = [nd.get('ref') for nd in elem.findall('nd')]
                    
                    tags = {}
                    for tag in elem.findall('tag'):
                        tags[tag.get('k')] = tag.get('v')
                    
                    if len(nd_refs) >= 2:
                        coords = []
                        for nd_ref in nd_refs:
                            if nd_ref in nodes:
                                coords.append(nodes[nd_ref])
                        
                        if len(coords) >= 2:
                            if coords[0] == coords[-1] and len(coords) >= 4:
                                try:
                                    geometry = Polygon(coords)
                                except:
                                    geometry = LineString(coords)
                            else:
                                geometry = LineString(coords)
                            
                            if 'building' in tags and tags['building'] not in ['no', 'None']:
                                buildings.append({
                                    'id': way_id,
                                    'geometry': geometry,
                                    **tags
                                })
                            
                            if 'highway' in tags:
                                roads.append({
                                    'id': way_id,
                                    'geometry': geometry,
                                    **tags
                                })
                    
                    elem.clear()
        
        return nodes, buildings, roads
    
    def _get_bounds_from_osm(self) -> Optional[Tuple[float, float, float, float]]:
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
    
    def _get_utm_zone(self, longitude: float) -> int:
        return int((longitude + 180) / 6) + 1
    
    def _reproject_to_utm(self, gdf: gpd.GeoDataFrame, crs_code: Optional[str] = None) -> gpd.GeoDataFrame:
        if crs_code:
            target_crs = pyproj.CRS.from_string(crs_code)
        else:
            bounds = gdf.total_bounds
            center_lon = (bounds[0] + bounds[2]) / 2
            center_lat = (bounds[1] + bounds[3]) / 2
            
            utm_zone = self._get_utm_zone(center_lon)
            hemisphere = 'north' if center_lat >= 0 else 'south'
            epsg_code = 32600 + utm_zone if hemisphere == 'north' else 32700 + utm_zone
            target_crs = pyproj.CRS.from_epsg(epsg_code)
        
        return gdf.to_crs(target_crs)
    
    def _create_buffer_union(self, gdf: gpd.GeoDataFrame, buffer_distance: float) -> Polygon:
        if len(gdf) == 0:
            return Polygon()
        
        buffered = gdf.geometry.buffer(buffer_distance)
        union = unary_union(buffered)
        
        if union.is_empty:
            return Polygon()
        
        return union
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        input_path = kwargs.get("input_geojson_path")
        buffer_distance = kwargs.get("buffer_distance", 500.0)
        utm_crs = kwargs.get("utm_crs")
        
        # 参数验证
        if not input_path:
            return {
                "success": False,
                "error": "缺少必需参数: input_geojson_path"
            }
        
        os.makedirs(RESULT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = RESULT_DIR / f"buffer_filter_{buffer_distance}m_{timestamp}.geojson"
        
        # 读取输入的GeoJSON文件
        input_gdf = gpd.read_file(input_path)
        
        if input_gdf.empty:
            os.makedirs(output_path.parent, exist_ok=True)
            input_gdf.to_file(output_path, driver='GeoJSON')
            return {
                "success": True,
                "result_path": str(output_path),
                "region_count": 0,
                "total_area_m2": 0.0
            }
        
        # 从OSM文件读取建筑和道路数据
        nodes, buildings, roads = self._parse_osm_file()
        
        building_gdf = gpd.GeoDataFrame(buildings, crs='EPSG:4326') if buildings else gpd.GeoDataFrame([], crs='EPSG:4326')
        road_gdf = gpd.GeoDataFrame(roads, crs='EPSG:4326') if roads else gpd.GeoDataFrame([], crs='EPSG:4326')
        
        # 投影到UTM坐标系（用于计算缓冲区）
        input_gdf_utm = self._reproject_to_utm(input_gdf, utm_crs)
        target_utm_crs = input_gdf_utm.crs
        
        building_gdf_utm = self._reproject_to_utm(building_gdf, utm_crs) if len(building_gdf) > 0 else gpd.GeoDataFrame([], crs=target_utm_crs)
        road_gdf_utm = self._reproject_to_utm(road_gdf, utm_crs) if len(road_gdf) > 0 else gpd.GeoDataFrame([], crs=target_utm_crs)
        
        # 创建建筑和道路缓冲区
        building_buffer = self._create_buffer_union(building_gdf_utm, buffer_distance) if len(building_gdf) > 0 else Polygon()
        road_buffer = self._create_buffer_union(road_gdf_utm, buffer_distance) if len(road_gdf) > 0 else Polygon()
        
        # 合并缓冲区
        if building_buffer.is_empty and road_buffer.is_empty:
            excluded_areas = Polygon()
        elif building_buffer.is_empty:
            excluded_areas = road_buffer
        elif road_buffer.is_empty:
            excluded_areas = building_buffer
        else:
            excluded_areas = unary_union([building_buffer, road_buffer])
        
        # 筛选：从输入区域中排除建筑和道路缓冲区
        filtered_geometries = []
        for idx, row in input_gdf_utm.iterrows():
            geom = row.geometry
            if excluded_areas.is_empty:
                filtered_geom = geom
            else:
                filtered_geom = geom.difference(excluded_areas)
            
            if filtered_geom.is_empty:
                continue
            
            # 处理MultiPolygon
            if hasattr(filtered_geom, 'geoms'):
                for sub_geom in filtered_geom.geoms:
                    if not sub_geom.is_empty:
                        filtered_geometries.append(sub_geom)
            elif isinstance(filtered_geom, Polygon):
                filtered_geometries.append(filtered_geom)
        
        if not filtered_geometries:
            empty_gdf = gpd.GeoDataFrame([], crs=target_utm_crs)
            empty_gdf = empty_gdf.to_crs('EPSG:4326')
            os.makedirs(output_path.parent, exist_ok=True)
            empty_gdf.to_file(output_path, driver='GeoJSON')
            return {
                "success": True,
                "result_path": str(output_path),
                "region_count": 0,
                "total_area_m2": 0.0
            }
        
        # 创建筛选后的GeoDataFrame
        filtered_gdf_utm = gpd.GeoDataFrame(
            [{'geometry': geom, 'area_m2': geom.area} for geom in filtered_geometries],
            crs=target_utm_crs
        )
        
        # 转换回WGS84坐标系
        filtered_gdf = filtered_gdf_utm.to_crs('EPSG:4326')
        filtered_gdf['area_km2'] = filtered_gdf['area_m2'] / 1000000
        
        # 保存结果
        os.makedirs(output_path.parent, exist_ok=True)
        filtered_gdf.to_file(output_path, driver='GeoJSON')
        
        return {
            "success": True,
            "result_path": str(output_path),
            "region_count": len(filtered_gdf),
            "total_area_m2": float(filtered_gdf['area_m2'].sum()) if not filtered_gdf.empty else 0.0
        }
    
    def validate_params(self, **kwargs) -> bool:
        return kwargs.get("input_geojson_path") is not None