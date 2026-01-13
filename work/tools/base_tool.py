from abc import ABC, abstractmethod
from typing import Dict, Any
import geopandas as gpd
from shapely.geometry import Polygon, box
from config import GEO_BOUNDS
import numpy as np


class BaseTool(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.parameters = {}
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        pass
    
    def validate_params(self, **kwargs) -> bool:
        return True
    
    def get_schema(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
    
    def clip_to_bounds(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """将GeoDataFrame裁剪到配置的地理边界范围内"""
        if gdf is None or gdf.empty:
            return gdf
        
        # 创建边界多边形
        bounds = GEO_BOUNDS
        boundary = Polygon([
            (bounds["min_lon"], bounds["min_lat"]),
            (bounds["max_lon"], bounds["min_lat"]),
            (bounds["max_lon"], bounds["max_lat"]),
            (bounds["min_lon"], bounds["max_lat"]),
            (bounds["min_lon"], bounds["min_lat"])
        ])
        
        # 确保gdf使用WGS84坐标系
        if gdf.crs is None:
            gdf.set_crs('EPSG:4326', inplace=True)
        elif gdf.crs.to_string() != 'EPSG:4326':
            gdf = gdf.to_crs('EPSG:4326')
        
        # 创建边界GeoDataFrame
        boundary_gdf = gpd.GeoDataFrame([{'geometry': boundary}], crs='EPSG:4326')
        
        # 裁剪
        clipped_gdf = gpd.clip(gdf, boundary_gdf)
        
        return clipped_gdf
    
    def subdivide_large_regions(self, gdf: gpd.GeoDataFrame, max_area_km2: float = 1.0) -> gpd.GeoDataFrame:
        """
        将大面积区域细分成更小的网格，以便后续筛选工具能更精确地工作
        
        Args:
            gdf: 输入的GeoDataFrame
            max_area_km2: 最大允许的区域面积（平方公里），超过此面积将被细分
            
        Returns:
            细分后的GeoDataFrame
        """
        if gdf is None or gdf.empty:
            return gdf
        
        # 确保gdf使用WGS84坐标系
        if gdf.crs is None:
            gdf.set_crs('EPSG:4326', inplace=True)
        elif gdf.crs.to_string() != 'EPSG:4326':
            gdf = gdf.to_crs('EPSG:4326')
        
        # 投影到UTM坐标系计算面积
        bounds = gdf.total_bounds
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        # 计算UTM区号
        utm_zone = int((center_lon + 180) / 6) + 1
        hemisphere = 'north' if center_lat >= 0 else 'south'
        epsg_code = 32600 + utm_zone if hemisphere == 'north' else 32700 + utm_zone
        
        gdf_utm = gdf.to_crs(f'EPSG:{epsg_code}')
        
        subdivided_geometries = []
        subdivided_data = []
        
        for idx, row in gdf_utm.iterrows():
            geom = row.geometry
            area_km2 = geom.area / 1000000  # 转换为平方公里
            
            # 如果区域面积小于阈值，直接保留
            if area_km2 <= max_area_km2:
                subdivided_geometries.append(geom)
                # 保存其他属性
                row_dict = row.to_dict()
                row_dict.pop('geometry', None)
                subdivided_data.append(row_dict)
            else:
                # 需要细分：创建网格
                bounds = geom.bounds
                minx, miny, maxx, maxy = bounds
                
                # 计算网格大小（使每个网格约等于max_area_km2）
                grid_size = np.sqrt(max_area_km2 * 1000000)  # 转换为平方米，然后开方得到边长
                
                # 创建网格
                x_coords = np.arange(minx, maxx, grid_size)
                y_coords = np.arange(miny, maxy, grid_size)
                
                if len(x_coords) == 0:
                    x_coords = np.array([minx, maxx])
                else:
                    x_coords = np.append(x_coords, maxx)
                
                if len(y_coords) == 0:
                    y_coords = np.array([miny, maxy])
                else:
                    y_coords = np.append(y_coords, maxy)
                
                # 生成网格单元
                for i in range(len(x_coords) - 1):
                    for j in range(len(y_coords) - 1):
                        grid_cell = box(x_coords[i], y_coords[j], x_coords[i+1], y_coords[j+1])
                        # 与原始几何图形求交
                        intersection = geom.intersection(grid_cell)
                        if not intersection.is_empty and intersection.area > 0:
                            subdivided_geometries.append(intersection)
                            # 保存其他属性
                            row_dict = row.to_dict()
                            row_dict.pop('geometry', None)
                            subdivided_data.append(row_dict)
        
        if not subdivided_geometries:
            return gdf
        
        # 创建新的GeoDataFrame
        subdivided_gdf_utm = gpd.GeoDataFrame(
            subdivided_data,
            geometry=subdivided_geometries,
            crs=gdf_utm.crs
        )
        
        # 转换回WGS84
        subdivided_gdf = subdivided_gdf_utm.to_crs('EPSG:4326')
        
        # 重新计算面积
        subdivided_gdf_utm = subdivided_gdf.to_crs(f'EPSG:{epsg_code}')
        subdivided_gdf['area_m2'] = subdivided_gdf_utm.geometry.area
        subdivided_gdf['area_km2'] = subdivided_gdf['area_m2'] / 1000000
        subdivided_gdf = subdivided_gdf.to_crs('EPSG:4326')
        
        return subdivided_gdf
