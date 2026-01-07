"""
查看KAG checkpoint中提取的实体和关系数据
"""
import os
import sys
import json
import shelve
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

# 添加KAG路径
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from kag.interface.common.model.sub_graph import SubGraph, Node, Edge
    SUBGRAPH_AVAILABLE = True
except ImportError:
    try:
        from kag.builder.model.sub_graph import SubGraph
        from kag.builder.model.node import Node
        from kag.builder.model.edge import Edge
        SUBGRAPH_AVAILABLE = True
    except ImportError:
        print("警告：无法导入KAG模型，将使用字典方式解析数据")
        SubGraph = None
        SUBGRAPH_AVAILABLE = False


def read_txt_checkpoint(ckpt_path: Path) -> Dict[str, Any]:
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
        print(f"读取文本checkpoint失败 {ckpt_path}: {e}")
    
    return data


def read_bin_checkpoint(ckpt_path: Path) -> Dict[str, Any]:
    """读取二进制格式的checkpoint文件（shelve）"""
    data = {}
    if not ckpt_path.exists():
        return data
    
    try:
        # 尝试作为shelve文件读取
        with shelve.open(str(ckpt_path), "r") as db:
            for key in db.keys():
                data[key] = db[key]
    except Exception as e:
        # 如果不是shelve格式，尝试读取.val文件
        try:
            import pickle
            with open(ckpt_path, "rb") as f:
                data = pickle.load(f)
        except Exception as e2:
            print(f"读取二进制checkpoint失败 {ckpt_path}: {e}, {e2}")
    
    return data


def read_diskcache_checkpoint(cache_dir: Path) -> Dict[str, Any]:
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
                # 调试：打印前几个key的类型
                if len(data) <= 3:
                    print(f"    Key: {key}, Type: {type(value)}, Value preview: {str(value)[:200]}")
            except Exception as e:
                print(f"读取cache key {key} 失败: {e}")
        cache.close()
    except Exception as e:
        print(f"读取DiskCache失败 {cache_dir}: {e}")
    
    return data


def parse_subgraph(data: Any) -> Dict[str, Any]:
    """解析SubGraph数据"""
    # 如果是列表，可能是多个SubGraph或BuilderComponentData
    if isinstance(data, list):
        all_nodes = []
        all_edges = []
        for item in data:
            # 先检查是否是SubGraph对象
            if SUBGRAPH_AVAILABLE and SubGraph and isinstance(item, SubGraph):
                parsed = parse_subgraph(item)  # 递归处理SubGraph对象
                if "nodes" in parsed:
                    all_nodes.extend(parsed["nodes"])
                if "edges" in parsed:
                    all_edges.extend(parsed["edges"])
            elif isinstance(item, dict):
                # 检查是否是字典格式的SubGraph数据
                # 检查是否有resultEdges（这是LLM返回的原始格式）
                if "resultEdges" in item:
                    # 转换LLM返回的格式到标准格式
                    edges = item.get("resultEdges", [])
                    for edge in edges:
                        # 转换格式：from -> from_id, to -> to_id
                        formatted_edge = {
                            "from_id": edge.get("from", edge.get("from_id", "")),
                            "from_type": edge.get("fromType", edge.get("from_type", "")),
                            "label": edge.get("label", ""),
                            "to_id": edge.get("to", edge.get("to_id", "")),
                            "to_type": edge.get("toType", edge.get("to_type", "")),
                            "properties": edge.get("properties", {})
                        }
                        all_edges.append(formatted_edge)
                
                # 检查是否有resultNodes
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
                        # 如果id为空，使用name作为id
                        if not formatted_node["id"]:
                            formatted_node["id"] = node.get("name", "")
                        all_nodes.append(formatted_node)
                
                # 检查标准格式
                if "nodes" in item:
                    all_nodes.extend(item["nodes"])
                if "edges" in item:
                    all_edges.extend(item["edges"])
            else:
                # 递归解析其他类型
                parsed = parse_subgraph(item)
                if "nodes" in parsed:
                    all_nodes.extend(parsed["nodes"])
                if "edges" in parsed:
                    all_edges.extend(parsed["edges"])
        return {"nodes": all_nodes, "edges": all_edges}
    
    if isinstance(data, dict):
        # 如果是字典，检查是否有nodes和edges
        if "nodes" in data or "edges" in data:
            return data
        # 检查是否有resultEdges/resultNodes格式
        if "resultEdges" in data or "resultNodes" in data:
            return parse_subgraph([data])  # 转换为列表格式处理
        # 可能是SubGraph的字典表示
        if "data" in data:
            return parse_subgraph(data["data"])
        return data
    elif SUBGRAPH_AVAILABLE and SubGraph and isinstance(data, SubGraph):
        # 如果是SubGraph对象，转换为字典
        try:
            result = data.to_dict()
            # SubGraph.to_dict()返回的是resultNodes和resultEdges格式
            # 转换为标准格式
            nodes = []
            edges = []
            if "resultNodes" in result:
                for node in result["resultNodes"]:
                    formatted_node = {
                        "id": node.get("id", node.get("name", "")),
                        "label": node.get("label", ""),
                        "properties": node.get("properties", {})
                    }
                    if "name" in node:
                        formatted_node["properties"]["name"] = node["name"]
                    # 如果id为空，使用name作为id
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
            print(f"      to_dict()失败: {e}")
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
            return parse_subgraph(attrs["data"])
    
    return {"nodes": [], "edges": []}


def extract_entities_and_relations(ckpt_dir: Path) -> Dict[str, Any]:
    """从checkpoint目录中提取所有实体和关系"""
    all_entities = []
    all_relations = []
    entity_types = defaultdict(int)
    relation_types = defaultdict(int)
    
    # 1. 读取主checkpoint文件
    main_ckpt = ckpt_dir / "kag_checkpoint_0_1.ckpt"
    if main_ckpt.exists():
        print(f"\n读取主checkpoint文件: {main_ckpt}")
        main_data = read_txt_checkpoint(main_ckpt)
        print(f"  找到 {len(main_data)} 条记录")
        
        for key, value in main_data.items():
            if isinstance(value, (dict, list)) or (SubGraph and isinstance(value, SubGraph)):
                graph_data = parse_subgraph(value)
                if "nodes" in graph_data:
                    for node in graph_data["nodes"]:
                        all_entities.append(node)
                        if isinstance(node, dict):
                            entity_types[node.get("label", "Unknown")] += 1
                        elif hasattr(node, "label"):
                            entity_types[node.label] += 1
                if "edges" in graph_data:
                    for edge in graph_data["edges"]:
                        all_relations.append(edge)
                        if isinstance(edge, dict):
                            relation_types[edge.get("label", "Unknown")] += 1
                        elif hasattr(edge, "label"):
                            relation_types[edge.label] += 1
    
    # 2. 读取KAGPostProcessor的checkpoint（这里应该包含处理后的实体和关系）
    postprocessor_dir = ckpt_dir / "KAGPostProcessor"
    if postprocessor_dir.exists():
        print(f"\n读取KAGPostProcessor checkpoint: {postprocessor_dir}")
        # 读取cache.db
        cache_data = read_diskcache_checkpoint(postprocessor_dir)
        print(f"  找到 {len(cache_data)} 条记录")
        
        for key, value in cache_data.items():
            graph_data = parse_subgraph(value)
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])
            if nodes or edges:
                print(f"  处理key: {key[:50]}... -> nodes={len(nodes)}, edges={len(edges)}")
            if nodes:
                for node in nodes:
                    all_entities.append(node)
                    if isinstance(node, dict):
                        entity_types[node.get("label", "Unknown")] += 1
                    elif hasattr(node, "label"):
                        entity_types[node.label] += 1
            if edges:
                for edge in edges:
                    all_relations.append(edge)
                    if isinstance(edge, dict):
                        relation_types[edge.get("label", "Unknown")] += 1
                    elif hasattr(edge, "label"):
                        relation_types[edge.label] += 1
        
        # 读取.val文件
        for val_file in postprocessor_dir.rglob("*.val"):
            try:
                import pickle
                with open(val_file, "rb") as f:
                    val_data = pickle.load(f)
                    graph_data = parse_subgraph(val_data)
                    if "nodes" in graph_data:
                        for node in graph_data["nodes"]:
                            all_entities.append(node)
                            if isinstance(node, dict):
                                entity_types[node.get("label", "Unknown")] += 1
                    if "edges" in graph_data:
                        for edge in graph_data["edges"]:
                            all_relations.append(edge)
                            if isinstance(edge, dict):
                                relation_types[edge.get("label", "Unknown")] += 1
            except Exception as e:
                print(f"  读取 {val_file} 失败: {e}")
    
    # 3. 读取KnowledgeUnitSchemaFreeExtractor的checkpoint（这里包含原始提取的实体和关系）
    extractor_dir = ckpt_dir / "KnowledgeUnitSchemaFreeExtractor"
    if extractor_dir.exists():
        print(f"\n读取KnowledgeUnitSchemaFreeExtractor checkpoint: {extractor_dir}")
        cache_data = read_diskcache_checkpoint(extractor_dir)
        print(f"  找到 {len(cache_data)} 条记录")
        
        for key, value in cache_data.items():
            graph_data = parse_subgraph(value)
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])
            if nodes or edges:
                print(f"  处理key: {key[:50]}... -> nodes={len(nodes)}, edges={len(edges)}")
            if nodes:
                for node in nodes:
                    all_entities.append(node)
                    if isinstance(node, dict):
                        entity_types[node.get("label", "Unknown")] += 1
                    elif hasattr(node, "label"):
                        entity_types[node.label] += 1
            if edges:
                for edge in edges:
                    all_relations.append(edge)
                    if isinstance(edge, dict):
                        relation_types[edge.get("label", "Unknown")] += 1
                    elif hasattr(edge, "label"):
                        relation_types[edge.label] += 1
    
    return {
        "entities": all_entities,
        "relations": all_relations,
        "entity_types": dict(entity_types),
        "relation_types": dict(relation_types)
    }


def format_entity(entity: Any) -> Dict[str, Any]:
    """格式化实体数据"""
    if isinstance(entity, dict):
        return {
            "id": entity.get("id", ""),
            "label": entity.get("label", ""),
            "properties": entity.get("properties", {})
        }
    elif hasattr(entity, "__dict__"):
        return {
            "id": getattr(entity, "id", ""),
            "label": getattr(entity, "label", ""),
            "properties": getattr(entity, "properties", {})
        }
    else:
        return {"id": str(entity), "label": "", "properties": {}}


def format_relation(relation: Any) -> Dict[str, Any]:
    """格式化关系数据"""
    if isinstance(relation, dict):
        return {
            "from_id": relation.get("from_id", ""),
            "from_type": relation.get("from_type", ""),
            "label": relation.get("label", ""),
            "to_id": relation.get("to_id", ""),
            "to_type": relation.get("to_type", ""),
            "properties": relation.get("properties", {})
        }
    elif hasattr(relation, "__dict__"):
        return {
            "from_id": getattr(relation, "from_id", ""),
            "from_type": getattr(relation, "from_type", ""),
            "label": getattr(relation, "label", ""),
            "to_id": getattr(relation, "to_id", ""),
            "to_type": getattr(relation, "to_type", ""),
            "properties": getattr(relation, "properties", {})
        }
    else:
        return {
            "from_id": "",
            "from_type": "",
            "label": "",
            "to_id": "",
            "to_type": "",
            "properties": {}
        }


def print_results(results: Dict[str, Any], limit: int = 50):
    """打印结果"""
    print("\n" + "=" * 80)
    print("KAG Checkpoint 数据统计")
    print("=" * 80)
    
    print(f"\n实体总数: {len(results['entities'])}")
    print(f"关系总数: {len(results['relations'])}")
    
    print(f"\n实体类型统计:")
    for entity_type, count in sorted(results['entity_types'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {entity_type}: {count}")
    
    print(f"\n关系类型统计:")
    for relation_type, count in sorted(results['relation_types'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {relation_type}: {count}")
    
    # 显示前N个实体
    print(f"\n前 {min(limit, len(results['entities']))} 个实体:")
    print("-" * 80)
    for i, entity in enumerate(results['entities'][:limit], 1):
        formatted = format_entity(entity)
        print(f"\n[{i}] 实体ID: {formatted['id']}")
        print(f"    类型: {formatted['label']}")
        props = formatted['properties']
        if props:
            print(f"    属性:")
            for key, value in list(props.items())[:5]:  # 只显示前5个属性
                if not key.startswith("_"):  # 跳过内部属性
                    print(f"      {key}: {value}")
    
    # 显示前N个关系
    print(f"\n前 {min(limit, len(results['relations']))} 个关系:")
    print("-" * 80)
    for i, relation in enumerate(results['relations'][:limit], 1):
        formatted = format_relation(relation)
        print(f"\n[{i}] {formatted['from_id']} ({formatted['from_type']}) "
              f"--[{formatted['label']}]--> "
              f"{formatted['to_id']} ({formatted['to_type']})")
        props = formatted['properties']
        if props:
            print(f"    属性:")
            for key, value in list(props.items())[:3]:  # 只显示前3个属性
                if not key.startswith("_"):
                    print(f"      {key}: {value}")


def save_to_json(results: Dict[str, Any], output_file: Path):
    """保存结果到JSON文件"""
    # 格式化数据以便JSON序列化
    formatted_results = {
        "summary": {
            "total_entities": len(results['entities']),
            "total_relations": len(results['relations']),
            "entity_types": results['entity_types'],
            "relation_types": results['relation_types']
        },
        "entities": [format_entity(e) for e in results['entities']],
        "relations": [format_relation(r) for r in results['relations']]
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(formatted_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存到: {output_file}")


def main():
    """主函数"""
    # 获取checkpoint目录
    script_dir = Path(__file__).parent
    ckpt_dir = script_dir / "builder" / "ckpt"
    
    if not ckpt_dir.exists():
        print(f"错误：checkpoint目录不存在: {ckpt_dir}")
        return
    
    print(f"正在读取checkpoint目录: {ckpt_dir}")
    
    # 提取数据
    results = extract_entities_and_relations(ckpt_dir)
    
    # 打印结果
    print_results(results, limit=50)
    
    # 保存到JSON文件
    output_file = script_dir / "ckpt_extracted_data.json"
    save_to_json(results, output_file)
    
    print("\n" + "=" * 80)
    print("完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()

