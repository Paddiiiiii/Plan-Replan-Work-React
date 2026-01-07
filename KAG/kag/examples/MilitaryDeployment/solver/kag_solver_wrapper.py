"""
KAG推理问答接口包装器
用于外层系统调用KAG推理能力
"""
import logging
import sys
import asyncio
import json
import shelve
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

class KAGSolverWrapper:
    """KAG推理问答接口包装器"""
    
    def __init__(self, project_path: Optional[str] = None):
        """
        初始化KAG推理器
        
        Args:
            project_path: KAG项目路径，默认为当前目录（MilitaryDeployment）
        """
        if project_path is None:
            # 默认使用当前目录（MilitaryDeployment项目目录）
            self.project_path = Path(__file__).parent.parent
        else:
            self.project_path = Path(project_path)
        
        self._solver = None
        self._initialized = False
    
    def _init_solver(self):
        """延迟初始化solver，避免导入错误"""
        if self._initialized:
            return
        
        try:
            # 添加KAG路径
            # self.project_path = KAG/kag/examples/MilitaryDeployment
            # parent.parent.parent = KAG
            kag_path = self.project_path.parent.parent.parent
            if str(kag_path) not in sys.path:
                sys.path.insert(0, str(kag_path))
            
            # 导入KAG模块
            from kag.common.registry import import_modules_from_path
            from kag.common.conf import KAG_CONFIG
            from kag.interface import SolverPipelineABC
            
            # 设置工作目录为项目目录
            import os
            original_cwd = os.getcwd()
            try:
                os.chdir(str(self.project_path))
                
                # 显式初始化KAG_CONFIG，加载kag_config.yaml
                config_file = self.project_path / "kag_config.yaml"
                if not config_file.exists():
                    raise FileNotFoundError(
                        f"配置文件不存在: {config_file}"
                    )
                
                # 初始化KAG_CONFIG
                KAG_CONFIG.initialize(prod=False, config_file=str(config_file))
                
                # 导入项目模块（注册自定义组件等）
                import_modules_from_path(".")
                
                # 检查配置是否存在
                solver_config = KAG_CONFIG.all_config.get("kag_solver_pipeline")
                if not solver_config:
                    raise ValueError(
                        f"kag_solver_pipeline配置不存在。"
                        f"请检查 {config_file} 文件。"
                        f"当前配置keys: {list(KAG_CONFIG.all_config.keys())}"
                    )
                
                # 从配置创建solver pipeline
                self._solver = SolverPipelineABC.from_config(solver_config)
                
                self._initialized = True
                logger.info("KAG推理器初始化成功")
            finally:
                os.chdir(original_cwd)
                
        except Exception as e:
            logger.error(f"KAG推理器初始化失败: {e}", exc_info=True)
            self._solver = None
            self._initialized = True  # 标记为已初始化，避免重复尝试
    
    def query(self, question: str) -> Dict:
        """
        使用KAG推理引擎回答问题（同步版本）
        
        Args:
            question: 用户问题
            
        Returns:
            包含答案和引用的字典
        """
        self._init_solver()
        
        if self._solver is None:
            logger.warning("KAG推理器未初始化，返回空结果")
            return {
                "answer": "",
                "references": [],
                "error": "KAG推理器未初始化"
            }
        
        try:
            # 检查是否已经在事件循环中
            try:
                loop = asyncio.get_running_loop()
                # 如果已经在事件循环中，不能使用asyncio.run()
                # 在新线程中运行异步代码
                import concurrent.futures
                
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(self._solver.ainvoke(question))
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    result = future.result(timeout=300)  # 5分钟超时
            except RuntimeError:
                # 没有运行的事件循环，可以使用asyncio.run()
                result = asyncio.run(self._solver.ainvoke(question))
            
            # 标准化返回格式
            # KAG的返回格式通常是字符串（答案）
            if isinstance(result, str):
                return {
                    "answer": result,
                    "references": [],
                    "raw_result": result
                }
            elif isinstance(result, dict):
                return {
                    "answer": result.get("answer", str(result) if result else ""),
                    "references": result.get("references", []),
                    "raw_result": result
                }
            else:
                return {
                    "answer": str(result) if result else "",
                    "references": [],
                    "raw_result": result
                }
        except Exception as e:
            logger.error(f"KAG推理查询失败: {e}", exc_info=True)
            return {
                "answer": "",
                "references": [],
                "error": str(e)
            }
    
    async def aquery(self, question: str) -> Dict:
        """
        使用KAG推理引擎回答问题（异步版本）
        
        Args:
            question: 用户问题
            
        Returns:
            包含答案和引用的字典
        """
        self._init_solver()
        
        if self._solver is None:
            logger.warning("KAG推理器未初始化，返回空结果")
            return {
                "answer": "",
                "references": [],
                "error": "KAG推理器未初始化"
            }
        
        try:
            # 异步版本直接await
            result = await self._solver.ainvoke(question)
            
            # 标准化返回格式
            if isinstance(result, str):
                return {
                    "answer": result,
                    "references": [],
                    "raw_result": result
                }
            elif isinstance(result, dict):
                return {
                    "answer": result.get("answer", str(result) if result else ""),
                    "references": result.get("references", []),
                    "raw_result": result
                }
            else:
                return {
                    "answer": str(result) if result else "",
                    "references": [],
                    "raw_result": result
                }
        except Exception as e:
            logger.error(f"KAG推理查询失败: {e}", exc_info=True)
            return {
                "answer": "",
                "references": [],
                "error": str(e)
            }
    
    def query_with_context(self, question: str, context: Optional[List[Dict]] = None) -> Dict:
        """
        带上下文的KAG推理查询
        
        Args:
            question: 用户问题
            context: 额外的上下文信息（可选）
            
        Returns:
            包含答案和引用的字典
        """
        # 如果有上下文，可以将其整合到问题中
        if context:
            context_text = "\n".join([ctx.get("text", "") for ctx in context])
            enhanced_question = f"{question}\n\n相关上下文：\n{context_text}"
        else:
            enhanced_question = question
        
        return self.query(enhanced_question)
    
    def get_kg_data(self) -> Dict:
        """
        从checkpoint文件读取知识图谱数据（实体和关系）
        
        Returns:
            包含实体和关系的字典
        """
        try:
            # checkpoint目录路径
            ckpt_dir = self.project_path / "builder" / "ckpt"
            
            if not ckpt_dir.exists():
                logger.warning(f"Checkpoint目录不存在: {ckpt_dir}")
                return {
                    "entities": [],
                    "relations": [],
                    "entity_count": 0,
                    "relation_count": 0,
                    "error": f"Checkpoint目录不存在: {ckpt_dir}"
                }
            
            # 提取实体和关系
            result = self._extract_entities_and_relations(ckpt_dir)
            
            # 格式化数据
            formatted_entities = []
            formatted_relations = []
            
            raw_entities = result.get("entities", [])
            raw_relations = result.get("relations", [])
            logger.info(f"原始数据: {len(raw_entities)} 个实体, {len(raw_relations)} 个关系")
            
            # 去重实体（基于id）
            entity_map = {}
            skipped_entities = 0
            for entity in raw_entities:
                entity_id = self._get_entity_id(entity)
                if entity_id and entity_id not in entity_map:
                    formatted_entity = self._format_entity(entity)
                    if formatted_entity:
                        entity_map[entity_id] = formatted_entity
                        formatted_entities.append(formatted_entity)
                    else:
                        skipped_entities += 1
                        logger.debug(f"跳过实体格式化失败: {type(entity)}, {str(entity)[:100]}")
                elif not entity_id:
                    skipped_entities += 1
                    logger.debug(f"跳过实体（无ID）: {type(entity)}, {str(entity)[:100]}")
            
            # 格式化关系
            skipped_relations = 0
            for relation in raw_relations:
                formatted_relation = self._format_relation(relation)
                if formatted_relation:
                    formatted_relations.append(formatted_relation)
                else:
                    skipped_relations += 1
                    logger.debug(f"跳过关系格式化失败: {type(relation)}, {str(relation)[:100]}")
            
            logger.info(f"从checkpoint提取到 {len(formatted_entities)} 个实体, {len(formatted_relations)} 个关系")
            if skipped_entities > 0 or skipped_relations > 0:
                logger.warning(f"跳过了 {skipped_entities} 个实体, {skipped_relations} 个关系（格式化失败或无ID）")
            
            return {
                "entities": formatted_entities,
                "relations": formatted_relations,
                "entity_count": len(formatted_entities),
                "relation_count": len(formatted_relations)
            }
            
        except Exception as e:
            logger.error(f"获取知识图谱数据失败: {e}", exc_info=True)
            return {
                "entities": [],
                "relations": [],
                "entity_count": 0,
                "relation_count": 0,
                "error": str(e)
            }
    
    def _extract_entities_and_relations(self, ckpt_dir: Path) -> Dict[str, Any]:
        """从checkpoint目录中提取所有实体和关系"""
        all_entities = []
        all_relations = []
        
        # 尝试导入SubGraph类
        SubGraph = None
        try:
            from kag.interface.common.model.sub_graph import SubGraph as SG1
            SubGraph = SG1
        except ImportError:
            try:
                from kag.builder.model.sub_graph import SubGraph as SG2
                SubGraph = SG2
            except ImportError:
                logger.debug("无法导入SubGraph类，将使用字典方式解析")
        
        # 1. 读取主checkpoint文件
        main_ckpt = ckpt_dir / "kag_checkpoint_0_1.ckpt"
        if main_ckpt.exists():
            logger.debug(f"读取主checkpoint文件: {main_ckpt}")
            main_data = self._read_txt_checkpoint(main_ckpt)
            logger.debug(f"主checkpoint找到 {len(main_data)} 条记录")
            for key, value in main_data.items():
                if isinstance(value, (dict, list)) or (SubGraph and isinstance(value, SubGraph)):
                    graph_data = self._parse_subgraph(value, SubGraph)
                    if "nodes" in graph_data:
                        all_entities.extend(graph_data["nodes"])
                        logger.debug(f"从主checkpoint提取到 {len(graph_data['nodes'])} 个节点")
                    if "edges" in graph_data:
                        all_relations.extend(graph_data["edges"])
                        logger.debug(f"从主checkpoint提取到 {len(graph_data['edges'])} 个边")
        
        # 2. 读取KAGPostProcessor的checkpoint（这里应该包含处理后的实体和关系）
        postprocessor_dir = ckpt_dir / "KAGPostProcessor"
        if postprocessor_dir.exists():
            logger.debug(f"读取KAGPostProcessor checkpoint: {postprocessor_dir}")
            cache_data = self._read_diskcache_checkpoint(postprocessor_dir)
            logger.debug(f"KAGPostProcessor找到 {len(cache_data)} 条记录")
            for key, value in cache_data.items():
                graph_data = self._parse_subgraph(value, SubGraph)
                nodes = graph_data.get("nodes", [])
                edges = graph_data.get("edges", [])
                if nodes:
                    all_entities.extend(nodes)
                    logger.debug(f"从KAGPostProcessor key {key[:50]}... 提取到 {len(nodes)} 个节点")
                if edges:
                    all_relations.extend(edges)
                    logger.debug(f"从KAGPostProcessor key {key[:50]}... 提取到 {len(edges)} 个边")
            
            # 读取.val文件
            for val_file in postprocessor_dir.rglob("*.val"):
                try:
                    import pickle
                    with open(val_file, "rb") as f:
                        val_data = pickle.load(f)
                        graph_data = self._parse_subgraph(val_data, SubGraph)
                        if "nodes" in graph_data:
                            all_entities.extend(graph_data["nodes"])
                        if "edges" in graph_data:
                            all_relations.extend(graph_data["edges"])
                except Exception as e:
                    logger.debug(f"读取 {val_file} 失败: {e}")
        
        # 3. 读取KnowledgeUnitSchemaFreeExtractor的checkpoint（这里包含原始提取的实体和关系）
        extractor_dir = ckpt_dir / "KnowledgeUnitSchemaFreeExtractor"
        if extractor_dir.exists():
            logger.debug(f"读取KnowledgeUnitSchemaFreeExtractor checkpoint: {extractor_dir}")
            cache_data = self._read_diskcache_checkpoint(extractor_dir)
            logger.debug(f"KnowledgeUnitSchemaFreeExtractor找到 {len(cache_data)} 条记录")
            for key, value in cache_data.items():
                graph_data = self._parse_subgraph(value, SubGraph)
                nodes = graph_data.get("nodes", [])
                edges = graph_data.get("edges", [])
                if nodes:
                    all_entities.extend(nodes)
                    logger.debug(f"从Extractor key {key[:50]}... 提取到 {len(nodes)} 个节点")
                if edges:
                    all_relations.extend(edges)
                    logger.debug(f"从Extractor key {key[:50]}... 提取到 {len(edges)} 个边")
        
        # 4. 读取KGWriter的checkpoint（可能包含最终写入的实体和关系）
        kgwriter_dir = ckpt_dir / "KGWriter"
        if kgwriter_dir.exists():
            logger.debug(f"读取KGWriter checkpoint: {kgwriter_dir}")
            cache_data = self._read_diskcache_checkpoint(kgwriter_dir)
            logger.debug(f"KGWriter找到 {len(cache_data)} 条记录")
            for key, value in cache_data.items():
                graph_data = self._parse_subgraph(value, SubGraph)
                nodes = graph_data.get("nodes", [])
                edges = graph_data.get("edges", [])
                if nodes:
                    all_entities.extend(nodes)
                    logger.debug(f"从KGWriter key {key[:50]}... 提取到 {len(nodes)} 个节点")
                if edges:
                    all_relations.extend(edges)
                    logger.debug(f"从KGWriter key {key[:50]}... 提取到 {len(edges)} 个边")
        
        logger.info(f"总共提取到 {len(all_entities)} 个实体, {len(all_relations)} 个关系")
        
        return {
            "entities": all_entities,
            "relations": all_relations
        }
    
    def _read_txt_checkpoint(self, ckpt_path: Path) -> Dict[str, Any]:
        """读取文本格式的checkpoint文件"""
        data = {}
        if not ckpt_path.exists():
            return data
        
        try:
            with open(ckpt_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if "id" in entry and "value" in entry:
                            data[entry["id"]] = entry["value"]
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.debug(f"读取文本checkpoint失败 {ckpt_path}: {e}")
        
        return data
    
    def _read_diskcache_checkpoint(self, cache_dir: Path) -> Dict[str, Any]:
        """读取DiskCache格式的checkpoint"""
        data = {}
        if not cache_dir.exists():
            return data
        
        try:
            from diskcache import Cache
            cache = Cache(str(cache_dir))
            for key in cache:
                try:
                    value = cache[key]
                    data[key] = value
                except Exception as e:
                    logger.debug(f"读取cache key {key} 失败: {e}")
            cache.close()
        except Exception as e:
            logger.debug(f"读取DiskCache失败 {cache_dir}: {e}")
        
        return data
    
    def _parse_subgraph(self, data: Any, SubGraph=None) -> Dict[str, Any]:
        """解析SubGraph数据"""
        # 如果是列表，可能是多个SubGraph或BuilderComponentData
        if isinstance(data, list):
            all_nodes = []
            all_edges = []
            for item in data:
                # 先检查是否是SubGraph对象
                if SubGraph and isinstance(item, SubGraph):
                    parsed = self._parse_subgraph(item, SubGraph)  # 递归处理SubGraph对象
                    if "nodes" in parsed:
                        all_nodes.extend(parsed["nodes"])
                    if "edges" in parsed:
                        all_edges.extend(parsed["edges"])
                elif isinstance(item, dict):
                    if "resultEdges" in item:
                        edges = item.get("resultEdges", [])
                        for edge in edges:
                            formatted_edge = {
                                "from_id": edge.get("from", edge.get("from_id", "")),
                                "from_type": edge.get("fromType", edge.get("from_type", "")),
                                "label": edge.get("label", ""),
                                "to_id": edge.get("to", edge.get("to_id", "")),
                                "to_type": edge.get("toType", edge.get("to_type", "")),
                                "properties": edge.get("properties", {})
                            }
                            all_edges.append(formatted_edge)
                    if "resultNodes" in item:
                        nodes = item.get("resultNodes", [])
                        for node in nodes:
                            formatted_node = {
                                "id": node.get("id", node.get("name", "")),
                                "label": node.get("type", node.get("label", "")),
                                "properties": node.get("properties", {})
                            }
                            if "name" in node:
                                formatted_node["properties"]["name"] = node["name"]
                            if not formatted_node["id"]:
                                formatted_node["id"] = node.get("name", "")
                            all_nodes.append(formatted_node)
                    if "nodes" in item:
                        all_nodes.extend(item["nodes"])
                    if "edges" in item:
                        all_edges.extend(item["edges"])
                else:
                    # 递归解析其他类型
                    parsed = self._parse_subgraph(item, SubGraph)
                    if "nodes" in parsed:
                        all_nodes.extend(parsed["nodes"])
                    if "edges" in parsed:
                        all_edges.extend(parsed["edges"])
            return {"nodes": all_nodes, "edges": all_edges}
        
        if isinstance(data, dict):
            if "nodes" in data or "edges" in data:
                return data
            if "resultEdges" in data or "resultNodes" in data:
                return self._parse_subgraph([data], SubGraph)
            if "data" in data:
                return self._parse_subgraph(data["data"], SubGraph)
            return data
        elif SubGraph and isinstance(data, SubGraph):
            # 如果是SubGraph对象，转换为字典
            try:
                result = data.to_dict()
                # SubGraph.to_dict()返回的是resultNodes和resultEdges格式
                nodes = []
                edges = []
                if "resultNodes" in result:
                    for node in result["resultNodes"]:
                        formatted_node = {
                            "id": node.get("id", node.get("name", "")),
                            "label": node.get("label", node.get("type", "")),
                            "properties": node.get("properties", {})
                        }
                        if "name" in node:
                            formatted_node["properties"]["name"] = node["name"]
                        if not formatted_node["id"]:
                            formatted_node["id"] = node.get("name", "")
                        nodes.append(formatted_node)
                elif "nodes" in result:
                    nodes = result["nodes"]
                else:
                    # 尝试从对象属性获取
                    node_objs = getattr(data, "nodes", [])
                    for node in node_objs:
                        if isinstance(node, dict):
                            nodes.append(node)
                        elif hasattr(node, "to_dict"):
                            nodes.append(node.to_dict())
                        else:
                            nodes.append({
                                "id": getattr(node, "id", ""),
                                "label": getattr(node, "label", ""),
                                "properties": getattr(node, "properties", {})
                            })
                
                if "resultEdges" in result:
                    for edge in result["resultEdges"]:
                        formatted_edge = {
                            "from_id": edge.get("from", edge.get("from_id", "")),
                            "from_type": edge.get("fromType", edge.get("from_type", "")),
                            "label": edge.get("label", ""),
                            "to_id": edge.get("to", edge.get("to_id", "")),
                            "to_type": edge.get("toType", edge.get("to_type", "")),
                            "properties": edge.get("properties", {})
                        }
                        edges.append(formatted_edge)
                elif "edges" in result:
                    edges = result["edges"]
                else:
                    # 尝试从对象属性获取
                    edge_objs = getattr(data, "edges", [])
                    for edge in edge_objs:
                        if isinstance(edge, dict):
                            edges.append(edge)
                        elif hasattr(edge, "to_dict"):
                            edges.append(edge.to_dict())
                        else:
                            edges.append({
                                "from_id": getattr(edge, "from_id", ""),
                                "from_type": getattr(edge, "from_type", ""),
                                "label": getattr(edge, "label", ""),
                                "to_id": getattr(edge, "to_id", ""),
                                "to_type": getattr(edge, "to_type", ""),
                                "properties": getattr(edge, "properties", {})
                            })
                
                return {"nodes": nodes, "edges": edges}
            except Exception as e:
                logger.debug(f"SubGraph.to_dict()失败: {e}")
                return {
                    "nodes": getattr(data, "nodes", []),
                    "edges": getattr(data, "edges", [])
                }
        elif hasattr(data, "to_dict"):
            # 如果有to_dict方法
            try:
                return data.to_dict()
            except:
                pass
        elif hasattr(data, "__dict__"):
            # 尝试从对象属性获取
            attrs = data.__dict__
            if "nodes" in attrs or "edges" in attrs:
                return {
                    "nodes": getattr(data, "nodes", []),
                    "edges": getattr(data, "edges", [])
                }
            # 检查是否是BuilderComponentData包装
            if "data" in attrs:
                return self._parse_subgraph(attrs["data"], SubGraph)
        
        return {"nodes": [], "edges": []}
    
    def _get_entity_id(self, entity: Any) -> str:
        """获取实体的唯一ID"""
        if isinstance(entity, dict):
            # 尝试多种方式获取ID
            entity_id = (entity.get("id") or entity.get("name") or 
                        entity.get("_id") or entity.get("identifier", ""))
            # 如果还是没有，尝试从properties中获取
            if not entity_id:
                props = entity.get("properties", {})
                entity_id = props.get("id") or props.get("name") or ""
            return str(entity_id) if entity_id else ""
        elif hasattr(entity, "id"):
            return str(getattr(entity, "id", ""))
        elif hasattr(entity, "name"):
            return str(getattr(entity, "name", ""))
        elif hasattr(entity, "__dict__"):
            attrs = entity.__dict__
            return str(attrs.get("id", attrs.get("name", "")))
        return ""
    
    def _format_entity(self, entity: Any) -> Optional[Dict]:
        """格式化实体数据"""
        try:
            if isinstance(entity, dict):
                # 尝试多种方式获取ID
                entity_id = entity.get("id") or entity.get("name") or entity.get("_id") or ""
                if not entity_id:
                    # 如果还是没有，尝试从properties中获取
                    props = entity.get("properties", {})
                    entity_id = props.get("id") or props.get("name") or ""
                
                # 尝试多种方式获取类型
                entity_type = entity.get("label") or entity.get("type") or entity.get("_type") or "Unknown"
                
                # 获取属性
                properties = entity.get("properties", {})
                if not properties and isinstance(entity, dict):
                    # 如果properties为空，尝试从entity本身提取属性（排除特殊字段）
                    exclude_keys = {"id", "name", "label", "type", "_id", "_type", "nodes", "edges"}
                    properties = {k: v for k, v in entity.items() if k not in exclude_keys}
                
                # 获取名称
                entity_name = properties.get("name") or entity.get("name") or entity_id
                
                # 确保properties中有name
                if "name" not in properties:
                    properties["name"] = entity_name
                
                # 确保ID不为空
                if not entity_id:
                    entity_id = entity_name or f"entity_{hash(str(entity))}"
                
                return {
                    "id": str(entity_id),
                    "name": str(entity_name),
                    "type": str(entity_type),
                    "properties": properties if isinstance(properties, dict) else {}
                }
            elif hasattr(entity, "to_dict"):
                entity_dict = entity.to_dict()
                return self._format_entity(entity_dict)
            elif hasattr(entity, "__dict__"):
                attrs = entity.__dict__
                entity_id = str(attrs.get("id", attrs.get("name", "")))
                entity_name = str(attrs.get("name", attrs.get("id", entity_id)))
                entity_type = str(attrs.get("label", attrs.get("type", "Unknown")))
                properties = dict(attrs.get("properties", {}))
                if "name" not in properties:
                    properties["name"] = entity_name
                return {
                    "id": entity_id,
                    "name": entity_name,
                    "type": entity_type,
                    "properties": properties
                }
        except Exception as e:
            logger.debug(f"格式化实体失败: {e}, entity类型: {type(entity)}")
        
        return None
    
    def _format_relation(self, relation: Any) -> Optional[Dict]:
        """格式化关系数据"""
        try:
            if isinstance(relation, dict):
                # 尝试多种方式获取source和target
                source = (relation.get("from_id") or relation.get("from") or 
                         relation.get("source") or relation.get("_from") or "")
                target = (relation.get("to_id") or relation.get("to") or 
                         relation.get("target") or relation.get("_to") or "")
                
                # 如果source/target是对象，尝试提取ID
                if isinstance(source, dict):
                    source = source.get("id") or source.get("name") or ""
                if isinstance(target, dict):
                    target = target.get("id") or target.get("name") or ""
                
                relation_type = (relation.get("label") or relation.get("type") or 
                               relation.get("_type") or "Unknown")
                properties = relation.get("properties", {})
                if not properties and isinstance(relation, dict):
                    # 如果properties为空，尝试从relation本身提取属性
                    exclude_keys = {"from_id", "from", "to_id", "to", "source", "target", 
                                   "label", "type", "_from", "_to", "_type"}
                    properties = {k: v for k, v in relation.items() if k not in exclude_keys}
                
                # 确保source和target都是字符串
                source = str(source) if source else ""
                target = str(target) if target else ""
                
                if source and target:
                    return {
                        "source": source,
                        "target": target,
                        "type": str(relation_type),
                        "properties": properties if isinstance(properties, dict) else {}
                    }
            elif hasattr(relation, "to_dict"):
                relation_dict = relation.to_dict()
                return self._format_relation(relation_dict)
            elif hasattr(relation, "__dict__"):
                attrs = relation.__dict__
                source = str(attrs.get("from_id", attrs.get("from", attrs.get("source", ""))))
                target = str(attrs.get("to_id", attrs.get("to", attrs.get("target", ""))))
                if source and target:
                    return {
                        "source": source,
                        "target": target,
                        "type": str(attrs.get("label", attrs.get("type", "Unknown"))),
                        "properties": dict(attrs.get("properties", {}))
                    }
        except Exception as e:
            logger.debug(f"格式化关系失败: {e}, relation类型: {type(relation)}")
        
        return None

