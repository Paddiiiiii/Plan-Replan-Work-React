# -*- coding: utf-8 -*-
"""
增强的实体-关系图可视化工具
支持原文高亮、抽取过程展示和炫酷的视觉效果
"""
import json
import re
import html
from typing import Dict, List, Optional, Any
from pathlib import Path

from kag.builder.model.sub_graph import SubGraph, Node, Edge
from kag.builder.model.chunk import Chunk


class EnhancedGraphVisualizer:
    """增强的图可视化工具，支持原文高亮和抽取过程展示"""
    
    def __init__(self):
        self.entity_colors = {}
        self.relation_colors = {}
        self.extraction_steps = []
        
    def visualize(
        self,
        subgraph: SubGraph,
        source_text: Optional[str] = None,
        source_chunk: Optional[Chunk] = None,
        extraction_steps: Optional[List[Dict]] = None,
        output_path: str = "enhanced_graph_visualization",
    ):
        """
        创建增强的可视化
        
        Args:
            subgraph: 要可视化的子图
            source_text: 原始文本（可选）
            source_chunk: 原始Chunk对象（可选，如果提供会自动提取文本）
            extraction_steps: 抽取过程步骤列表（可选）
            output_path: 输出文件路径（不含扩展名）
        """
        # 获取原文
        if source_text is None and source_chunk is not None:
            source_text = source_chunk.content
        
        # 准备数据（对大数据集进行采样）
        # 用户要求：至少显示100个节点，确保必须有显示内容
        total_nodes = len(subgraph.nodes)
        total_edges = len(subgraph.edges)
        
        # 强制至少显示100个节点（如果总数少于100，显示全部）
        # 为了确保能够显示，使用更保守的限制
        min_display_nodes = min(100, total_nodes)  # 至少100个，但不超过总数
        
        # 动态限制，但确保至少显示min_display_nodes个节点
        if total_nodes > 300 or total_edges > 1000:
            # 大数据集：显示100-200节点，300-500边（确保有显示）
            max_nodes = max(min_display_nodes, min(200, total_nodes))
            max_edges = max(200, min(500, total_edges))
        elif total_nodes > 150 or total_edges > 600:
            # 中等数据集：显示100-300节点，400-600边
            max_nodes = max(min_display_nodes, min(300, total_nodes))
            max_edges = max(300, min(600, total_edges))
        else:
            # 小数据集：显示全部或接近全部，但至少100个
            max_nodes = max(min_display_nodes, min(500, total_nodes))
            max_edges = max(200, min(800, total_edges))
        
        # 使用渐进式加载策略：从少量开始逐步增加，确保至少能显示一些数据
        print(f"[DEBUG] 开始渐进式加载，总共 {total_nodes} 个节点, {total_edges} 条边")
        graph_data = self._prepare_graph_data_incremental(subgraph)
        
        # 最终验证：确保至少有节点（用户要求必须要有显示）
        if not graph_data.get("nodes") or len(graph_data.get("nodes", [])) == 0:
            print(f"[CRITICAL] 渐进式加载后仍然无节点，使用绝对最小值（前10个节点）")
            # 最后的保险：至少取前10个节点
            if subgraph.nodes:
                fallback_nodes = list(subgraph.nodes)[:10]
                fallback_edges = list(subgraph.edges)[:30]
                
                nodes = []
                for node in fallback_nodes:
                    nodes.append({
                        "id": str(node.id),
                        "label": str(node.name) if node.name else str(node.id),
                        "type": str(node.label) if node.label else "Unknown",
                        "color": "#888888",
                        "properties": node.properties or {},
                        "size": 20,
                        "degree": 0
                    })
                
                edges = []
                node_ids = {str(n.id) for n in fallback_nodes}
                for edge in fallback_edges:
                    from_id = str(edge.from_id)
                    to_id = str(edge.to_id)
                    if from_id in node_ids and to_id in node_ids:
                        edges.append({
                            "from": from_id,
                            "to": to_id,
                            "label": str(edge.label) if edge.label else "",
                            "color": "#666666",
                            "properties": edge.properties or {}
                        })
                
                entity_types = set(n["type"] for n in nodes)
                relation_types = set(e["label"] for e in edges if e["label"])
                
                graph_data = {
                    "nodes": nodes,
                    "edges": edges,
                    "nodeTypes": list(entity_types),
                    "relationTypes": list(relation_types),
                    "stats": {
                        "total_nodes": total_nodes,
                        "total_edges": total_edges,
                        "displayed_nodes": len(nodes),
                        "displayed_edges": len(edges),
                        "sampled": True
                    }
                }
        highlighted_text = self._highlight_text(source_text, subgraph) if source_text else None
        steps_data = extraction_steps or self._generate_default_steps(subgraph)
        
        # 生成HTML
        html_content = self._generate_html(graph_data, highlighted_text, steps_data)
        
        # 保存文件
        output_file = Path(output_path).with_suffix('.html')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"增强可视化已保存到: {output_file}")
        return str(output_file)
    
    def _prepare_graph_data_incremental(self, subgraph: SubGraph) -> Dict:
        """
        渐进式准备图数据：从少量开始逐步增加，确保至少能显示一些数据
        
        策略：
        1. 从10个节点开始
        2. 逐步增加节点数（10, 20, 30, ..., 100, 150, 200, ...）
        3. 对于每个节点数，尝试添加对应的边
        4. 验证数据格式，确保节点和边都是有效的
        5. 返回最大能成功显示的数据量
        """
        total_nodes = len(subgraph.nodes)
        total_edges = len(subgraph.edges)
        
        # 统计节点的连接度
        node_degree = {}
        for edge in subgraph.edges:
            node_degree[edge.from_id] = node_degree.get(edge.from_id, 0) + 1
            node_degree[edge.to_id] = node_degree.get(edge.to_id, 0) + 1
        
        # 计算节点重要性
        node_scores = {}
        for node in subgraph.nodes:
            degree = node_degree.get(node.id, 0)
            importance = degree * 10 + len(node.properties) * 2
            node_scores[node.id] = importance
        
        # 按重要性排序
        sorted_nodes = sorted(subgraph.nodes, key=lambda n: node_scores.get(n.id, 0), reverse=True)
        
        # 渐进式尝试：支持大数据集，逐步增加到全部节点
        # 对于大数据集，使用更大的步长
        if total_nodes <= 100:
            test_counts = [10, 20, 30, 50, 75, 100]
        elif total_nodes <= 500:
            test_counts = [50, 100, 200, 300, 400, 500]
        elif total_nodes <= 1000:
            test_counts = [100, 200, 300, 500, 700, 1000]
        else:
            # 超大数据集：使用更大的步长，但确保能显示全部
            test_counts = [200, 400, 600, 800, 1000, 1500, 2000]
        
        # 确保不超过总数，并包含全部节点
        test_counts = [n for n in test_counts if n <= total_nodes]
        if not test_counts or test_counts[-1] < total_nodes:
            test_counts.append(total_nodes)
        
        best_nodes = []
        best_edges = []
        best_node_count = 0
        best_edge_count = 0
        
        print(f"[DEBUG] 开始渐进式加载，总共 {total_nodes} 个节点, {total_edges} 条边")
        
        for node_count in test_counts:
            # 选择节点
            selected_nodes = sorted_nodes[:node_count]
            selected_node_ids = {node.id for node in selected_nodes}  # 保持原始类型，不做字符串转换
            
            # 筛选连接到这些节点的边（直接使用原始ID比较）
            candidate_edges = []
            for edge in subgraph.edges:
                from_id = getattr(edge, 'from_id', None)
                to_id = getattr(edge, 'to_id', None)
                if from_id in selected_node_ids and to_id in selected_node_ids:
                    candidate_edges.append(edge)
            
            # 限制边数：对于大数据集，允许更多边
            # 边数大约是节点数的2-4倍，但不超过总边数
            if total_nodes > 500:
                max_edge_for_nodes = min(node_count * 4, len(candidate_edges), len(subgraph.edges))
            else:
                max_edge_for_nodes = min(node_count * 3, len(candidate_edges), len(subgraph.edges))
            
            # 按重要性排序边
            if candidate_edges:
                edge_importance = {}
                for edge in candidate_edges:
                    from_score = node_scores.get(edge.from_id, 0)
                    to_score = node_scores.get(edge.to_id, 0)
                    edge_importance[id(edge)] = from_score + to_score
                sorted_edges = sorted(candidate_edges, key=lambda e: edge_importance.get(id(e), 0), reverse=True)
                candidate_edges = sorted_edges[:max_edge_for_nodes]
            
            # 直接使用节点和边数据，不做过多验证（参考markdown_to_graph.py的方式）
            valid_nodes = []
            valid_edges = []
            
            # 处理节点：直接使用，类似Pyvis的add_node方式
            for node in selected_nodes:
                # 直接使用node.id，不做字符串转换验证
                node_id = node.id
                node_name = getattr(node, 'name', None) or str(node_id)
                node_label = getattr(node, 'label', None) or "Unknown"
                
                valid_nodes.append({
                    "id": node_id,  # 保持原始类型，vis.js会自动处理
                    "label": node_name,
                    "type": node_label,
                    "color": "#888888",  # 临时颜色
                    "properties": getattr(node, 'properties', None) or {},
                    "size": 20,
                    "degree": node_degree.get(node.id, 0)
                })
            
            # 处理边：直接使用，类似Pyvis的add_edge方式
            node_ids_set = {node.id for node in selected_nodes}
            for edge in candidate_edges:
                from_id = getattr(edge, 'from_id', None)
                to_id = getattr(edge, 'to_id', None)
                
                # 只验证from和to是否在节点列表中
                if from_id in node_ids_set and to_id in node_ids_set:
                    valid_edges.append({
                        "from": from_id,  # 保持原始类型
                        "to": to_id,
                        "label": getattr(edge, 'label', None) or "",
                        "color": "#666666",  # 临时颜色
                        "properties": getattr(edge, 'properties', None) or {}
                    })
            
            # 如果节点数为0，停止（用户要求）
            if len(valid_nodes) == 0:
                print(f"[WARNING] 节点数为0，停止增加，使用上次结果: {best_node_count} 个节点")
                break
            
            # 保存当前结果
            best_nodes = valid_nodes
            best_edges = valid_edges
            best_node_count = len(valid_nodes)
            best_edge_count = len(valid_edges)
            
            print(f"[DEBUG] 成功加载 {best_node_count} 个节点, {best_edge_count} 条边")
        
        # 如果还是没有节点，至少取前10个
        if not best_nodes and subgraph.nodes:
            print(f"[WARNING] 渐进式加载无结果，使用前10个节点作为最小值")
            fallback_nodes = list(subgraph.nodes)[:10]
            best_nodes = []
            node_ids_set = {str(n.id) for n in fallback_nodes}
            
            for node in fallback_nodes:
                best_nodes.append({
                    "id": str(node.id),
                    "label": str(node.name) if node.name else str(node.id),
                    "type": str(node.label) if node.label else "Unknown",
                    "color": "#888888",
                    "properties": node.properties or {},
                    "size": 20,
                    "degree": 0
                })
            
            # 添加连接到这些节点的边
            for edge in subgraph.edges[:100]:
                from_id = str(edge.from_id)
                to_id = str(edge.to_id)
                if from_id in node_ids_set and to_id in node_ids_set:
                    best_edges.append({
                        "from": from_id,
                        "to": to_id,
                        "label": str(edge.label) if edge.label else "",
                        "color": "#666666",
                        "properties": edge.properties or {}
                    })
                    if len(best_edges) >= 30:
                        break
        
        # 为节点和边分配颜色
        if best_nodes:
            entity_types = set(node["type"] for node in best_nodes if node["type"])
            colors = self._generate_color_palette(len(entity_types)) if entity_types else ["#888888"]
            type_colors = dict(zip(entity_types, colors)) if entity_types else {}
            
            for node in best_nodes:
                node["color"] = type_colors.get(node["type"], "#888888")
        
        if best_edges:
            relation_types = set(edge["label"] for edge in best_edges if edge["label"])
            rel_colors = self._generate_relation_colors(len(relation_types)) if relation_types else ["#666666"]
            rel_type_colors = dict(zip(relation_types, rel_colors)) if relation_types else {}
            
            for edge in best_edges:
                edge["color"] = rel_type_colors.get(edge["label"], "#666666")
        
        # 返回统计信息
        stats = {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "displayed_nodes": len(best_nodes),
            "displayed_edges": len(best_edges),
            "sampled": len(best_nodes) < total_nodes or len(best_edges) < total_edges
        }
        
        # 确保entity_types和relation_types已定义
        entity_types = set(node["type"] for node in best_nodes) if best_nodes else set()
        relation_types = set(edge["label"] for edge in best_edges if edge["label"]) if best_edges else set()
        
        print(f"[INFO] 最终显示: {len(best_nodes)} 个节点, {len(best_edges)} 条边 (原始: {total_nodes} 节点, {total_edges} 边)")
        
        return {
            "nodes": best_nodes,
            "edges": best_edges,
            "nodeTypes": list(entity_types),
            "relationTypes": list(relation_types),
            "stats": stats
        }
    
    def _prepare_graph_data(self, subgraph: SubGraph, max_nodes: int = 100, max_edges: int = 300) -> Dict:
        """准备图数据，对大数据集进行采样
        
        Args:
            subgraph: 要可视化的子图
            max_nodes: 最大节点数（默认500，防止可视化过载）
            max_edges: 最大边数（默认1000，防止可视化过载）
        """
        nodes = []
        edges = []
        
        # 统计节点的连接度（度中心性）
        node_degree = {}
        for edge in subgraph.edges:
            node_degree[edge.from_id] = node_degree.get(edge.from_id, 0) + 1
            node_degree[edge.to_id] = node_degree.get(edge.to_id, 0) + 1
        
        # 计算每个节点的总连接度
        node_scores = {}
        for node in subgraph.nodes:
            degree = node_degree.get(node.id, 0)
            # 考虑节点本身的重要性（属性数量等）
            importance = degree * 10 + len(node.properties) * 2
            node_scores[node.id] = importance
        
        # 按重要性排序节点
        sorted_nodes = sorted(subgraph.nodes, key=lambda n: node_scores.get(n.id, 0), reverse=True)
        
        # 确保至少选择一些节点（如果节点太少，按重要性排序）
        # 用户要求：至少显示100个节点，如果总数少于100，显示全部
        actual_max_nodes = max(max_nodes, min(100, len(sorted_nodes)))  # 至少100个或全部（如果少于100）
        
        # 限制节点数量
        if len(sorted_nodes) > actual_max_nodes:
            selected_nodes = sorted_nodes[:actual_max_nodes]
        else:
            selected_nodes = sorted_nodes  # 如果总数少于限制，全部选择
        
        selected_node_ids = {node.id for node in selected_nodes}
        
        # 只保留连接到选中节点的边
        filtered_edges = [e for e in subgraph.edges 
                        if e.from_id in selected_node_ids and e.to_id in selected_node_ids]
        
        # 限制边数量，但确保至少有边显示
        if len(filtered_edges) > max_edges:
            # 优先保留连接度高的边
            edge_importance = {}
            for edge in filtered_edges:
                from_score = node_scores.get(edge.from_id, 0)
                to_score = node_scores.get(edge.to_id, 0)
                edge_importance[id(edge)] = from_score + to_score
            sorted_edges = sorted(filtered_edges, key=lambda e: edge_importance.get(id(e), 0), reverse=True)
            # 确保至少保留一些边
            actual_max_edges = max(max_edges, min(200, len(sorted_edges)))
            filtered_edges = sorted_edges[:actual_max_edges]
        else:
            # 如果边数少于限制，全部保留
            filtered_edges = filtered_edges
        
        # 确保至少有节点和边（如果可能的话）
        if not selected_nodes and subgraph.nodes:
            # 如果采样后没有节点，至少选择前100个
            selected_nodes = sorted_nodes[:min(100, len(sorted_nodes))]
            selected_node_ids = {node.id for node in selected_nodes}
            filtered_edges = [e for e in subgraph.edges 
                            if e.from_id in selected_node_ids and e.to_id in selected_node_ids][:max_edges]
        
        # 为不同类型的实体分配颜色
        entity_types = set(node.label for node in selected_nodes)
        colors = self._generate_color_palette(len(entity_types))
        type_colors = dict(zip(entity_types, colors))
        
        # 准备节点数据（确保ID是字符串）
        for node in selected_nodes:
            node_color = type_colors.get(node.label, "#888888")
            nodes.append({
                "id": str(node.id),  # vis.js要求ID是字符串
                "label": str(node.name) if node.name else str(node.id),
                "type": str(node.label) if node.label else "Unknown",
                "color": node_color,
                "properties": node.properties or {},
                "size": self._calculate_node_size(node),
                "degree": node_degree.get(node.id, 0)
            })
        
        # 准备边数据（确保from和to是字符串）
        relation_types = set(edge.label for edge in filtered_edges if edge.label) if filtered_edges else set()
        rel_colors = self._generate_relation_colors(len(relation_types)) if relation_types else []
        rel_type_colors = dict(zip(relation_types, rel_colors)) if relation_types else {}
        
        for edge in filtered_edges:
            edge_color = rel_type_colors.get(edge.label, "#666666")
            edges.append({
                "from": str(edge.from_id),  # vis.js要求ID是字符串
                "to": str(edge.to_id),
                "label": str(edge.label) if edge.label else "",
                "color": edge_color,
                "properties": edge.properties or {}
            })
        
        # 最终验证：确保至少有节点（用户要求至少100个）
        if not nodes:
            # 如果采样后还是没有节点，使用最简单的方法：直接取前100个
            print(f"[CRITICAL] 节点列表为空，强制使用前100个节点")
            if subgraph.nodes:
                # 直接取前100个节点，不排序
                fallback_nodes = list(subgraph.nodes)[:min(100, len(subgraph.nodes))]
                fallback_node_ids = {node.id for node in fallback_nodes}
                
                # 简单准备节点数据
                entity_types = set(node.label for node in fallback_nodes)
                colors = self._generate_color_palette(len(entity_types))
                type_colors = dict(zip(entity_types, colors))
                
                for node in fallback_nodes:
                    node_color = type_colors.get(node.label, "#888888")
                    nodes.append({
                        "id": str(node.id),  # 确保ID是字符串
                        "label": str(node.name) if node.name else str(node.id),
                        "type": str(node.label) if node.label else "Unknown",
                        "color": node_color,
                        "properties": node.properties or {},
                        "size": 20,
                        "degree": 0
                    })
                
                # 准备边数据（连接到这些节点的边）
                fallback_edges = []
                # 将fallback_node_ids转换为字符串集合以便比较
                fallback_node_ids_str = {str(nid) for nid in fallback_node_ids}
                
                for edge in subgraph.edges[:min(max_edges * 3, len(subgraph.edges))]:  # 取更多候选边以便过滤
                    from_id_str = str(edge.from_id)
                    to_id_str = str(edge.to_id)
                    
                    # 检查from_id和to_id是否在选中的节点中
                    if from_id_str in fallback_node_ids_str and to_id_str in fallback_node_ids_str:
                        fallback_edges.append(edge)
                        if len(fallback_edges) >= max_edges:
                            break
                
                relation_types = set(edge.label for edge in fallback_edges if edge.label)
                rel_colors = self._generate_relation_colors(len(relation_types))
                rel_type_colors = dict(zip(relation_types, rel_colors))
                
                for edge in fallback_edges:
                    edge_color = rel_type_colors.get(edge.label, "#666666")
                    edges.append({
                        "from": str(edge.from_id),
                        "to": str(edge.to_id),
                        "label": str(edge.label) if edge.label else "",
                        "color": edge_color,
                        "properties": edge.properties or {}
                    })
        
        # 确保节点ID和边ID都是字符串（vis.js要求）
        for node in nodes:
            node["id"] = str(node["id"])
            if "label" not in node or not node["label"]:
                node["label"] = str(node.get("name", node["id"]))
        
        for edge in edges:
            edge["from"] = str(edge["from"])
            edge["to"] = str(edge["to"])
        
        # 返回统计信息
        stats = {
            "total_nodes": len(subgraph.nodes),
            "total_edges": len(subgraph.edges),
            "displayed_nodes": len(nodes),
            "displayed_edges": len(edges),
            "sampled": len(subgraph.nodes) > max_nodes or len(subgraph.edges) > max_edges
        }
        
        # 验证数据
        if not nodes:
            print(f"[ERROR] 最终节点列表为空！原始节点数: {len(subgraph.nodes)}, 最大节点数: {max_nodes}")
        if not edges:
            print(f"[WARNING] 最终边列表为空！原始边数: {len(subgraph.edges)}, 最大边数: {max_edges}")
        
        print(f"[INFO] 准备可视化数据: {len(nodes)} 个节点, {len(edges)} 条边 (原始: {len(subgraph.nodes)} 节点, {len(subgraph.edges)} 边)")
        
        # 确保entity_types和relation_types已定义
        if nodes:
            final_entity_types = set(node.get("type", "Unknown") for node in nodes)
        else:
            final_entity_types = set()
        
        if edges:
            final_relation_types = set(edge.get("label", "") for edge in edges if edge.get("label"))
        else:
            final_relation_types = set()
        
        return {
            "nodes": nodes,
            "edges": edges,
            "nodeTypes": list(final_entity_types),
            "relationTypes": list(final_relation_types),
            "stats": stats
        }
    
    def _highlight_text(self, text: str, subgraph: SubGraph) -> Dict:
        """高亮文本中的实体和关系"""
        if not text:
            return None
        
        # 收集所有实体名称
        entity_names = {}
        for node in subgraph.nodes:
            name = node.name
            if name and name in text:
                if name not in entity_names:
                    entity_names[name] = {
                        "type": node.label,
                        "id": node.id,
                        "color": self._get_entity_color(node.label)
                    }
        
        # 按长度排序，优先匹配长名称
        sorted_entities = sorted(entity_names.items(), key=lambda x: len(x[0]), reverse=True)
        
        # 高亮文本
        highlighted_segments = []
        last_pos = 0
        
        # 找到所有实体位置
        matches = []
        for name, info in sorted_entities:
            pattern = re.escape(name)
            for match in re.finditer(pattern, text):
                matches.append({
                    "start": match.start(),
                    "end": match.end(),
                    "name": name,
                    "info": info
                })
        
        # 按位置排序
        matches.sort(key=lambda x: x["start"])
        
        # 合并重叠的匹配（保留最长的）
        non_overlapping = []
        for match in matches:
            if not non_overlapping:
                non_overlapping.append(match)
            else:
                last = non_overlapping[-1]
                if match["start"] >= last["end"]:
                    non_overlapping.append(match)
                elif match["end"] - match["start"] > last["end"] - last["start"]:
                    non_overlapping[-1] = match
        
        # 构建高亮文本
        for match in non_overlapping:
            if match["start"] > last_pos:
                highlighted_segments.append({
                    "text": text[last_pos:match["start"]],
                    "type": "normal"
                })
            highlighted_segments.append({
                "text": text[match["start"]:match["end"]],
                "type": "entity",
                "entityName": match["name"],
                "entityType": match["info"]["type"],
                "entityId": match["info"]["id"],
                "color": match["info"]["color"]
            })
            last_pos = match["end"]
        
        if last_pos < len(text):
            highlighted_segments.append({
                "text": text[last_pos:],
                "type": "normal"
            })
        
        return {
            "original": text,
            "segments": highlighted_segments,
            "entities": entity_names
        }
    
    def _generate_default_steps(self, subgraph: SubGraph) -> List[Dict]:
        """生成默认的抽取步骤"""
        steps = []
        
        # 步骤1: 实体识别
        entity_count = len(subgraph.nodes)
        steps.append({
            "step": 1,
            "name": "实体识别",
            "description": f"从文本中识别出 {entity_count} 个实体",
            "entities": [{"name": node.name, "type": node.label} for node in subgraph.nodes[:10]],
            "status": "completed"
        })
        
        # 步骤2: 关系抽取
        relation_count = len(subgraph.edges)
        steps.append({
            "step": 2,
            "name": "关系抽取",
            "description": f"抽取了 {relation_count} 条关系",
            "relations": [{"from": edge.from_id, "to": edge.to_id, "label": edge.label} 
                         for edge in subgraph.edges[:10]],
            "status": "completed"
        })
        
        # 步骤3: 图谱构建
        steps.append({
            "step": 3,
            "name": "图谱构建",
            "description": f"构建包含 {entity_count} 个节点和 {relation_count} 条边的知识图谱",
            "status": "completed"
        })
        
        return steps
    
    def _generate_color_palette(self, n: int) -> List[str]:
        """生成颜色调色板"""
        # 使用现代、炫酷的配色方案
        base_colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8",
            "#F7DC6F", "#BB8FCE", "#85C1E2", "#F8B739", "#52BE80",
            "#EC7063", "#5DADE2", "#58D68D", "#F4D03F", "#AF7AC5",
            "#85C1E9", "#F1948A", "#73C6B6", "#F7DC6F", "#A569BD"
        ]
        
        if n <= len(base_colors):
            return base_colors[:n]
        
        # 如果需要更多颜色，生成渐变色
        colors = base_colors.copy()
        for i in range(n - len(base_colors)):
            base_idx = i % len(base_colors)
            colors.append(self._adjust_brightness(base_colors[base_idx], (i // len(base_colors)) * 0.1))
        
        return colors[:n]
    
    def _generate_relation_colors(self, n: int) -> List[str]:
        """生成关系颜色"""
        base_colors = [
            "#9B59B6", "#3498DB", "#1ABC9C", "#E74C3C", "#F39C12",
            "#34495E", "#E67E22", "#16A085", "#C0392B", "#8E44AD"
        ]
        
        if n <= len(base_colors):
            return base_colors[:n]
        
        colors = base_colors.copy()
        for i in range(n - len(base_colors)):
            base_idx = i % len(base_colors)
            colors.append(self._adjust_brightness(base_colors[base_idx], (i // len(base_colors)) * 0.15))
        
        return colors[:n]
    
    def _adjust_brightness(self, hex_color: str, factor: float) -> str:
        """调整颜色亮度"""
        # 简化实现，实际可以使用更复杂的算法
        return hex_color
    
    def _get_entity_color(self, entity_type: str) -> str:
        """获取实体类型对应的颜色"""
        if entity_type not in self.entity_colors:
            colors = self._generate_color_palette(1)
            self.entity_colors[entity_type] = colors[0] if colors else "#888888"
        return self.entity_colors[entity_type]
    
    def _calculate_node_size(self, node: Node) -> int:
        """计算节点大小"""
        base_size = 20
        # 根据连接数调整大小
        return base_size + min(len(node.properties) * 2, 30)
    
    def _generate_html(self, graph_data: Dict, highlighted_text: Optional[Dict], steps_data: List[Dict]) -> str:
        """生成HTML内容"""
        html_template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KAG 知识图谱可视化 - 增强版</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Microsoft YaHei', 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        
        .container {
            max-width: 1800px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }
        
        .header .stats {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 20px;
            flex-wrap: wrap;
        }
        
        .stat-item {
            background: rgba(255, 255, 255, 0.2);
            padding: 15px 25px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }
        
        .stat-item .number {
            font-size: 2em;
            font-weight: bold;
            display: block;
        }
        
        .stat-item .label {
            font-size: 0.9em;
            opacity: 0.9;
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 20px;
        }
        
        @media (max-width: 1400px) {
            .main-content {
                grid-template-columns: 1fr;
            }
        }
        
        .panel {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }
        
        .panel-title {
            font-size: 1.5em;
            font-weight: bold;
            margin-bottom: 15px;
            color: #667eea;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .panel-title::before {
            content: "▸";
            font-size: 1.2em;
        }
        
        #graph-container {
            width: 100%;
            height: 600px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            background: #fafafa;
        }
        
        .text-panel {
            max-height: 600px;
            overflow-y: auto;
        }
        
        .highlighted-text {
            line-height: 1.8;
            font-size: 14px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        .text-normal {
            color: #333;
        }
        
        .text-entity {
            background: linear-gradient(120deg, #84fab0 0%, #8fd3f4 100%);
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            position: relative;
            display: inline-block;
            margin: 0 1px;
        }
        
        .text-entity:hover {
            transform: scale(1.1);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            z-index: 10;
        }
        
        .text-entity::after {
            content: attr(data-type);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            white-space: nowrap;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s;
            margin-bottom: 5px;
        }
        
        .text-entity:hover::after {
            opacity: 1;
        }
        
        .steps-panel {
            grid-column: 1 / -1;
            margin-top: 20px;
        }
        
        .steps-container {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .step-item {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 20px;
            border-radius: 10px;
            border-left: 5px solid #667eea;
            transition: all 0.3s;
            animation: slideIn 0.5s ease-out;
        }
        
        .step-item:hover {
            transform: translateX(10px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(-20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        .step-header {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 10px;
        }
        
        .step-number {
            background: #667eea;
            color: white;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.2em;
        }
        
        .step-name {
            font-size: 1.3em;
            font-weight: bold;
            color: #333;
        }
        
        .step-description {
            color: #666;
            margin-top: 10px;
            line-height: 1.6;
        }
        
        .step-entities, .step-relations {
            margin-top: 15px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        
        .entity-tag, .relation-tag {
            background: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.9em;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            transition: all 0.3s;
        }
        
        .entity-tag:hover, .relation-tag:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        }
        
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        
        .control-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
        }
        
        .control-btn:hover {
            background: #5568d3;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        }
        
        .legend {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .legend-color {
            width: 20px;
            height: 20px;
            border-radius: 4px;
        }
        
        .legend-label {
            font-size: 0.9em;
            color: #666;
        }
        
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #888;
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #555;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 KAG 知识图谱可视化</h1>
            <div class="stats">
                <div class="stat-item">
                    <span class="number" id="node-count">0</span>
                    <span class="label">实体节点</span>
                    <span class="label" id="node-total" style="font-size: 0.8em; opacity: 0.7;"></span>
                </div>
                <div class="stat-item">
                    <span class="number" id="edge-count">0</span>
                    <span class="label">关系边</span>
                    <span class="label" id="edge-total" style="font-size: 0.8em; opacity: 0.7;"></span>
                </div>
                <div class="stat-item">
                    <span class="number" id="type-count">0</span>
                    <span class="label">实体类型</span>
                </div>
            </div>
            <div id="sampling-notice" style="margin-top: 15px; padding: 10px; background: rgba(255, 255, 255, 0.2); border-radius: 5px; display: none;">
                <span style="font-size: 0.9em;">⚠️ 数据量较大，仅显示部分重要节点和关系（按连接度排序）</span>
            </div>
        </div>
        
        <div class="main-content">
            <div class="panel">
                <div class="panel-title">知识图谱</div>
                <div class="controls">
                    <button class="control-btn" onclick="resetView()">重置视图</button>
                    <button class="control-btn" onclick="fitView()">适应窗口</button>
                </div>
                <div id="graph-container"></div>
                <div class="legend" id="legend"></div>
            </div>
            
            <div class="panel">
                <div class="panel-title">原文高亮</div>
                <div class="text-panel">
                    <div class="highlighted-text" id="highlighted-text">
                        {highlighted_text_content}
                    </div>
                </div>
            </div>
            
            <div class="panel steps-panel">
                <div class="panel-title">抽取过程</div>
                <div class="steps-container" id="steps-container">
                    {steps_content}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // 图数据
        const graphData = {graph_data_json};
        const highlightedText = {highlighted_text_json};
        
        // 初始化网络图
        let network = null;
        let physicsEnabled = true; // 默认启用物理引擎
        let nodeCount = 0;
        let edgeCount = 0;
        
        function initGraph() {
            const container = document.getElementById('graph-container');
            
            // 详细的调试信息
            console.log("=== 开始初始化图表 ===");
            console.log("graphData:", graphData);
            console.log("graphData.nodes:", graphData.nodes);
            console.log("graphData.edges:", graphData.edges);
            console.log("节点数量:", graphData.nodes ? graphData.nodes.length : 0);
            console.log("边数量:", graphData.edges ? graphData.edges.length : 0);
            
            // 验证数据
            if (!graphData) {
                console.error("graphData 未定义");
                container.innerHTML = '<div style="padding: 20px; text-align: center; color: #f44336;"><h3>数据未定义</h3><p>graphData 变量未定义，请检查数据传递</p></div>';
                return;
            }
            
            if (!graphData.nodes || !Array.isArray(graphData.nodes)) {
                console.error("graphData.nodes 无效:", graphData.nodes);
                container.innerHTML = '<div style="padding: 20px; text-align: center; color: #f44336;"><h3>节点数据无效</h3><p>graphData.nodes 不是数组或不存在</p></div>';
                return;
            }
            
            if (graphData.nodes.length === 0) {
                console.error("节点数组为空");
                container.innerHTML = '<div style="padding: 20px; text-align: center; color: #f44336;"><h3>无节点数据</h3><p>节点数组为空，无法显示可视化</p><p>请检查数据源</p></div>';
                document.getElementById('node-count').textContent = '0';
                document.getElementById('edge-count').textContent = '0';
                document.getElementById('type-count').textContent = '0';
                return;
            }
            
            console.log("✅ 数据验证通过，开始创建节点和边");
            
            // 先计算数据规模（用于决定字体大小等）
            const nodeCount = graphData.nodes.length;
            const edgeCount = graphData.edges ? graphData.edges.length : 0;
            const isLargeGraph = nodeCount > 200 || edgeCount > 500;
            
            console.log(`数据规模: ${nodeCount} 节点, ${edgeCount} 边, 大数据集: ${isLargeGraph}`);
            
            // 处理节点数据，确保格式正确
            const processedNodes = [];
            for (let i = 0; i < graphData.nodes.length; i++) {
                const node = graphData.nodes[i];
                try {
                    // 验证节点数据：确保id存在且不为空
                    if (!node) {
                        console.warn(`节点 ${i} 为 null 或 undefined`);
                        continue;
                    }
                    
                    // 检查id是否存在且有效
                    const nodeId = node.id;
                    if (nodeId === null || nodeId === undefined || nodeId === '') {
                        console.warn(`节点 ${i} 的 id 无效:`, nodeId, node);
                        continue;
                    }
                    
                    // 直接使用节点数据，vis.js会自动处理（参考Pyvis方式）
                    const nodeId = node.id;
                    const nodeLabel = node.label || node.name || String(nodeId) || 'Unknown';
                    
                    processedNodes.push({
                        id: nodeId,  // vis.js支持字符串和数字，不做强制转换
                        label: String(nodeLabel),  // label必须是字符串
                        color: {
                            background: node.color || '#888888',
                            border: '#2B2B2B',
                            highlight: {
                                background: node.color || '#888888',
                                border: '#000000'
                            }
                        },
                        size: node.size || 20,
                        font: {
                            size: isLargeGraph ? 12 : 14,
                            face: 'Microsoft YaHei'
                        },
                        shape: 'box',
                        title: `${node.type || 'Unknown'}\\n${JSON.stringify(node.properties || {}, null, 2)}`
                    });
                } catch (error) {
                    console.error(`处理节点 ${i} 时出错:`, error, node);
                }
            }
            
            console.log(`处理后的节点数: ${processedNodes.length} / ${graphData.nodes.length}`);
            
            if (processedNodes.length === 0) {
                console.error("处理后的节点数为0，无法继续");
                container.innerHTML = '<div style="padding: 20px; text-align: center; color: #f44336;"><h3>节点数据处理失败</h3><p>所有节点数据处理后都无效</p><p>请检查数据格式</p></div>';
                return;
            }
            
            const nodes = new vis.DataSet(processedNodes);
            
            // 处理边数据，确保from和to都存在（使用处理后的节点ID，保持原始类型）
            const validEdges = [];
            const nodeIds = new Set(processedNodes.map(n => n.id));  // 保持原始类型，不做字符串转换
            
            console.log(`节点ID集合大小: ${nodeIds.size}`);
            if (nodeIds.size > 0) {
                console.log("前5个节点ID:", Array.from(nodeIds).slice(0, 5));
            }
            
            if (graphData.edges && graphData.edges.length > 0) {
                console.log(`开始处理 ${graphData.edges.length} 条边`);
                for (let i = 0; i < graphData.edges.length; i++) {
                    const edge = graphData.edges[i];
                    try {
                        // 直接使用edge.from和edge.to，vis.js会自动匹配（参考Pyvis方式）
                        const fromId = edge.from || edge.from_id;
                        const toId = edge.to || edge.to_id;
                        
                        // 确保from和to存在且在节点列表中（使用原始类型比较）
                        if (fromId !== null && fromId !== undefined && 
                            toId !== null && toId !== undefined &&
                            nodeIds.has(fromId) && nodeIds.has(toId)) {
                            validEdges.push({
                                from: fromId,  // 保持原始类型，vis.js会自动匹配
                                to: toId,
                                label: String(edge.label || ''),
                                color: {
                                    color: edge.color || "#666666",
                                    highlight: edge.color || "#666666"
                                },
                                width: isLargeGraph ? 1 : 2,
                                arrows: {
                                    to: {
                                        enabled: true,
                                        type: 'arrow'
                                    }
                                },
                                font: {
                                    size: isLargeGraph ? 10 : 12,
                                    face: 'Microsoft YaHei',
                                    align: 'middle'
                                },
                                smooth: {
                                    type: isLargeGraph ? 'straightCross' : 'cubicBezier',
                                    roundness: 0.4
                                }
                            });
                        }
                    } catch (error) {
                        console.warn(`处理边 ${i} 时出错:`, error, edge);
                    }
                }
                console.log(`✅ 有效边数: ${validEdges.length} / ${graphData.edges.length}`);
            } else {
                console.warn("边数据为空或不存在");
            }
            
            const edges = new vis.DataSet(validEdges);
            
            const data = { nodes: nodes, edges: edges };
            
            // 再次验证
            if (nodes.length === 0) {
                console.error("No valid nodes after processing");
                container.innerHTML = '<div style="padding: 20px; text-align: center; color: #f44336;"><h3>节点数据无效</h3><p>无法创建节点，请检查数据格式</p></div>';
                return;
            }
            
            console.log(`✅ 准备创建网络图: ${processedNodes.length} 个节点, ${validEdges.length} 条边`);
            
            // 根据数据量优化配置（使用实际处理后的数据）
            nodeCount = processedNodes.length;
            edgeCount = validEdges.length;
            const isLargeGraph = nodeCount > 200 || edgeCount > 500;
            const isVeryLargeGraph = nodeCount > 500 || edgeCount > 2000;
            
            console.log(`图规模: ${nodeCount} 节点, ${edgeCount} 边, 大数据集: ${isLargeGraph}, 超大数据集: ${isVeryLargeGraph}`);
            
            const options = {
                physics: {
                    enabled: physicsEnabled, // 根据用户选择启用/关闭物理引擎
                    stabilization: {
                        iterations: isVeryLargeGraph ? 100 : (isLargeGraph ? 150 : 200), // 大数据集适当减少迭代次数
                        updateInterval: isVeryLargeGraph ? 50 : (isLargeGraph ? 25 : 5),
                        onlyDynamicEdges: isVeryLargeGraph // 超大数据集只稳定动态边
                    },
                    barnesHut: {
                        gravitationalConstant: isVeryLargeGraph ? -3000 : -2000,
                        centralGravity: isVeryLargeGraph ? 0.2 : 0.3,
                        springLength: isVeryLargeGraph ? 100 : (isLargeGraph ? 150 : 200),
                        springConstant: isVeryLargeGraph ? 0.02 : (isLargeGraph ? 0.03 : 0.04),
                        damping: isVeryLargeGraph ? 0.15 : (isLargeGraph ? 0.12 : 0.09),
                        avoidOverlap: isVeryLargeGraph ? 1 : (isLargeGraph ? 1 : 0),
                        theta: isVeryLargeGraph ? 1.2 : 0.5 // 超大数据集使用更大的theta值提高性能
                    },
                    solver: 'barnesHut', // 始终使用barnesHut，性能更好
                    timestep: isVeryLargeGraph ? 0.25 : (isLargeGraph ? 0.35 : 0.5)
                },
                interaction: {
                    hover: !isVeryLargeGraph, // 超大数据集关闭悬停以提升性能
                    tooltipDelay: isVeryLargeGraph ? 300 : 100,
                    zoomView: true,
                    dragView: true,
                    selectConnectedEdges: !isVeryLargeGraph,
                    hideEdgesOnDrag: isVeryLargeGraph, // 超大数据集拖拽时隐藏边
                    hideEdgesOnZoom: isVeryLargeGraph // 超大数据集缩放时隐藏边
                },
                nodes: {
                    borderWidth: isVeryLargeGraph ? 1 : (isLargeGraph ? 1 : 2),
                    shadow: {
                        enabled: !isVeryLargeGraph, // 超大数据集关闭阴影
                        size: 10,
                        x: 5,
                        y: 5
                    },
                    font: {
                        size: isVeryLargeGraph ? 10 : (isLargeGraph ? 12 : 14),
                        face: 'Microsoft YaHei'
                    },
                    scaling: {
                        min: isVeryLargeGraph ? 8 : 10,
                        max: isVeryLargeGraph ? 25 : 30
                    },
                    chosen: {
                        node: function(values, id, selected, hovering) {
                            // 选中节点时高亮
                            if (selected || hovering) {
                                values.borderWidth = 3;
                                values.borderColor = '#667eea';
                            }
                        }
                    }
                },
                edges: {
                    shadow: {
                        enabled: !isVeryLargeGraph, // 超大数据集关闭阴影
                        size: 5
                    },
                    width: isVeryLargeGraph ? 0.5 : (isLargeGraph ? 1 : 2),
                    font: {
                        size: isVeryLargeGraph ? 8 : (isLargeGraph ? 10 : 12),
                        face: 'Microsoft YaHei'
                    },
                    smooth: {
                        type: isVeryLargeGraph ? 'straightCross' : (isLargeGraph ? 'straightCross' : 'cubicBezier'),
                        roundness: 0.4
                    },
                    chosen: {
                        edge: function(values, id, selected, hovering) {
                            // 选中边时高亮
                            if (selected || hovering) {
                                values.width = 3;
                            }
                        }
                    }
                },
                layout: {
                    improvedLayout: !isVeryLargeGraph, // 超大数据集使用快速布局
                    hierarchical: {
                        enabled: false // 不使用层次布局，使用力导向布局
                    }
                }
            };
            
            // 添加错误处理和性能优化
            try {
                network = new vis.Network(container, data, options);
                
                // 大数据集时优化性能
                if (isVeryLargeGraph || isLargeGraph) {
                    network.on("stabilizationProgress", function(params) {
                        // 显示稳定化进度
                        if (params.iterations % 10 === 0) {
                            console.log(`稳定化进度: ${params.iterations}/${params.total}`);
                        }
                        // 稳定化完成后，如果节点数很大，可以关闭物理引擎以提高性能
                        if (params.iterations === params.total && isVeryLargeGraph) {
                            // 超大数据集稳定化后自动关闭物理引擎
                            setTimeout(function() {
                                network.setOptions({ physics: false });
                                physicsEnabled = false;
                            }, 1000);
                        }
                    });
                }
                
                // 监听错误
                network.on("error", function(params) {
                    console.error("Network error:", params);
                });
            } catch (error) {
                console.error("Failed to initialize network:", error);
                container.innerHTML = '<div style="padding: 20px; text-align: center; color: #f44336;"><h3>可视化加载失败</h3><p>数据量过大，请尝试减少显示的数据量</p><p>节点数: ' + nodeCount + ', 边数: ' + edgeCount + '</p></div>';
                return;
            }
            
            // 更新统计信息（使用实际的数据长度）
            const displayedNodes = nodes.length;
            const displayedEdges = edges.length;
            
            console.log("Updating stats:", displayedNodes, "nodes,", displayedEdges, "edges");
            
            document.getElementById('node-count').textContent = displayedNodes;
            document.getElementById('edge-count').textContent = displayedEdges;
            document.getElementById('type-count').textContent = graphData.nodeTypes ? graphData.nodeTypes.length : 0;
            
            // 如果有采样信息，显示总数
            if (graphData.stats) {
                const stats = graphData.stats;
                const nodeTotalEl = document.getElementById('node-total');
                const edgeTotalEl = document.getElementById('edge-total');
                
                if (stats.total_nodes > displayedNodes && nodeTotalEl) {
                    nodeTotalEl.textContent = `(共 ${stats.total_nodes} 个)`;
                }
                if (stats.total_edges > displayedEdges && edgeTotalEl) {
                    edgeTotalEl.textContent = `(共 ${stats.total_edges} 条)`;
                }
                if (stats.sampled) {
                    const noticeEl = document.getElementById('sampling-notice');
                    if (noticeEl) {
                        noticeEl.style.display = 'block';
                    }
                }
            }
            
            // 如果数据为空，显示警告
            if (displayedNodes === 0) {
                console.error("No nodes to display!");
                container.innerHTML = '<div style="padding: 20px; text-align: center; color: #f44336;"><h3>无数据可显示</h3><p>节点数为0，请检查数据加载</p></div>';
            }
            
            // 创建图例
            createLegend();
            
            // 节点点击事件
            network.on("click", function(params) {
                if (params.nodes.length > 0) {
                    const nodeId = params.nodes[0];
                    highlightEntityInText(nodeId);
                }
            });
        }
        
        function createLegend() {
            const legendContainer = document.getElementById('legend');
            legendContainer.innerHTML = '';
            
            graphData.nodeTypes.forEach(type => {
                const node = graphData.nodes.find(n => n.type === type);
                if (node) {
                    const item = document.createElement('div');
                    item.className = 'legend-item';
                    item.innerHTML = `
                        <div class="legend-color" style="background: ${node.color}"></div>
                        <span class="legend-label">${type}</span>
                    `;
                    legendContainer.appendChild(item);
                }
            });
        }
        
        function highlightEntityInText(nodeId) {
            const node = graphData.nodes.find(n => n.id === nodeId);
            if (!node) return;
            
            // 高亮文本中的实体
            const textElements = document.querySelectorAll('.text-entity');
            textElements.forEach(el => {
                if (el.getAttribute('data-entity-id') === nodeId) {
                    el.style.background = 'linear-gradient(120deg, #ff6b6b 0%, #ee5a6f 100%)';
                    el.style.color = 'white';
                    setTimeout(() => {
                        el.style.background = '';
                        el.style.color = '';
                    }, 2000);
                }
            });
        }
        
        function resetView() {
            if (network) {
                network.fit();
            }
        }
        
        function fitView() {
            if (network) {
                network.fit({
                    animation: true
                });
            }
        }
        
        
        // 为原文高亮中的实体添加点击事件
        function setupHighlightedTextEvents() {
            const container = document.getElementById('highlighted-text');
            if (!container) return;
            
            // 为所有实体span添加点击事件
            const entitySpans = container.querySelectorAll('.text-entity');
            entitySpans.forEach(span => {
                const entityId = span.getAttribute('data-entity-id');
                if (entityId && !span.onclick) {
                    span.style.cursor = 'pointer';
                    span.onclick = () => {
                        // 点击实体时高亮图中的节点
                        if (network) {
                            // 先清除之前的选择
                            network.unselectAll();
                            // 选中并聚焦到该节点
                            network.selectNodes([entityId]);
                            network.focus(entityId, {
                                scale: 1.5,
                                animation: true
                            });
                        }
                    };
                }
            });
        }
        
        // 初始化
        window.addEventListener('DOMContentLoaded', function() {
            initGraph();
            // 延迟一下再设置事件，确保HTML已经加载
            setTimeout(function() {
                setupHighlightedTextEvents();
            }, 200);
        });
    </script>
</body>
</html>"""
        
        # 准备数据
        graph_data_json = json.dumps(graph_data, ensure_ascii=False, indent=2)
        
        # 准备高亮文本
        if highlighted_text and highlighted_text.get("segments"):
            highlighted_text_html = ""
            for segment in highlighted_text["segments"]:
                # HTML转义文本内容
                escaped_text = html.escape(segment["text"])
                if segment["type"] == "entity":
                    entity_id = html.escape(str(segment.get("entityId", "")))
                    entity_type = html.escape(str(segment.get("entityType", "")))
                    color = html.escape(str(segment.get("color", "#888888")))
                    highlighted_text_html += f'<span class="text-entity" data-entity-id="{entity_id}" data-type="{entity_type}" style="background: linear-gradient(120deg, {color}88 0%, {color}AA 100%); padding: 2px 4px; border-radius: 3px; cursor: pointer;">{escaped_text}</span>'
                else:
                    highlighted_text_html += f'<span class="text-normal">{escaped_text}</span>'
            
            # 如果没有生成任何内容，显示提示
            if not highlighted_text_html.strip():
                highlighted_text_html = '<span class="text-normal">原文内容为空</span>'
        else:
            highlighted_text_html = '<span class="text-normal">暂无原文内容</span>'
        
        # 调试信息
        print(f"[DEBUG] 原文高亮HTML长度: {len(highlighted_text_html)}")
        print(f"[DEBUG] 原文高亮是否有内容: {bool(highlighted_text and highlighted_text.get('segments'))}")
        
        highlighted_text_json = json.dumps(highlighted_text, ensure_ascii=False) if highlighted_text else "null"
        
        # 准备步骤内容
        steps_html = ""
        for step in steps_data:
            entities_html = ""
            if "entities" in step and step["entities"]:
                entities_html = '<div class="step-entities">'
                for entity in step["entities"][:20]:  # 限制显示数量
                    entity_name = html.escape(str(entity["name"]))
                    entity_type = html.escape(str(entity["type"]))
                    entities_html += f'<span class="entity-tag">{entity_name} ({entity_type})</span>'
                entities_html += '</div>'
            
            relations_html = ""
            if "relations" in step and step["relations"]:
                relations_html = '<div class="step-relations">'
                for rel in step["relations"][:20]:
                    rel_from = html.escape(str(rel["from"]))
                    rel_to = html.escape(str(rel["to"]))
                    rel_label = html.escape(str(rel["label"]))
                    relations_html += f'<span class="relation-tag">{rel_from} --[{rel_label}]--> {rel_to}</span>'
                relations_html += '</div>'
            
            step_num = html.escape(str(step["step"]))
            step_name = html.escape(str(step["name"]))
            step_desc = html.escape(str(step["description"]))
            steps_html += f'''
                <div class="step-item" style="animation-delay: {step["step"] * 0.1}s">
                    <div class="step-header">
                        <div class="step-number">{step_num}</div>
                        <div class="step-name">{step_name}</div>
                    </div>
                    <div class="step-description">{step_desc}</div>
                    {entities_html}
                    {relations_html}
                </div>
            '''
        
        # 替换模板中的占位符
        html_content = html_template.replace("{graph_data_json}", graph_data_json)
        html_content = html_content.replace("{highlighted_text_content}", highlighted_text_html)
        html_content = html_content.replace("{highlighted_text_json}", highlighted_text_json)
        html_content = html_content.replace("{steps_content}", steps_html)
        
        return html_content


def visualize_enhanced_graph(
    subgraph: SubGraph,
    source_text: Optional[str] = None,
    source_chunk: Optional[Chunk] = None,
    extraction_steps: Optional[List[Dict]] = None,
    output_path: str = "enhanced_graph_visualization",
):
    """
    增强的图可视化函数
    
    Args:
        subgraph: 要可视化的子图
        source_text: 原始文本（可选）
        source_chunk: 原始Chunk对象（可选）
        extraction_steps: 抽取过程步骤列表（可选）
        output_path: 输出文件路径（不含扩展名）
    
    Returns:
        生成的HTML文件路径
    """
    visualizer = EnhancedGraphVisualizer()
    return visualizer.visualize(
        subgraph=subgraph,
        source_text=source_text,
        source_chunk=source_chunk,
        extraction_steps=extraction_steps,
        output_path=output_path,
    )

