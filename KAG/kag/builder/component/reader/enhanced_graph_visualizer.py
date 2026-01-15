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
        
        # 准备数据
        graph_data = self._prepare_graph_data(subgraph)
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
    
    def _prepare_graph_data(self, subgraph: SubGraph) -> Dict:
        """准备图数据"""
        nodes = []
        edges = []
        
        # 为不同类型的实体分配颜色
        entity_types = set(node.label for node in subgraph.nodes)
        colors = self._generate_color_palette(len(entity_types))
        type_colors = dict(zip(entity_types, colors))
        
        # 准备节点数据
        for node in subgraph.nodes:
            node_color = type_colors.get(node.label, "#888888")
            nodes.append({
                "id": node.id,
                "label": node.name,
                "type": node.label,
                "color": node_color,
                "properties": node.properties,
                "size": self._calculate_node_size(node)
            })
        
        # 准备边数据
        relation_types = set(edge.label for edge in subgraph.edges)
        rel_colors = self._generate_relation_colors(len(relation_types))
        rel_type_colors = dict(zip(relation_types, rel_colors))
        
        for edge in subgraph.edges:
            edge_color = rel_type_colors.get(edge.label, "#666666")
            edges.append({
                "from": edge.from_id,
                "to": edge.to_id,
                "label": edge.label,
                "color": edge_color,
                "properties": edge.properties
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "nodeTypes": list(entity_types),
            "relationTypes": list(relation_types)
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
                </div>
                <div class="stat-item">
                    <span class="number" id="edge-count">0</span>
                    <span class="label">关系边</span>
                </div>
                <div class="stat-item">
                    <span class="number" id="type-count">0</span>
                    <span class="label">实体类型</span>
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="panel">
                <div class="panel-title">知识图谱</div>
                <div class="controls">
                    <button class="control-btn" onclick="resetView()">重置视图</button>
                    <button class="control-btn" onclick="fitView()">适应窗口</button>
                    <button class="control-btn" onclick="togglePhysics()">切换物理引擎</button>
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
        let physicsEnabled = true;
        
        function initGraph() {
            const container = document.getElementById('graph-container');
            
            const nodes = new vis.DataSet(graphData.nodes.map(node => ({
                id: node.id,
                label: node.label,
                color: {
                    background: node.color,
                    border: '#2B2B2B',
                    highlight: {
                        background: node.color,
                        border: '#000000'
                    }
                },
                size: node.size,
                font: {
                    size: 14,
                    face: 'Microsoft YaHei'
                },
                shape: 'box',
                title: `${node.type}\\n${JSON.stringify(node.properties, null, 2)}`
            })));
            
            const edges = new vis.DataSet(graphData.edges.map(edge => ({
                from: edge.from,
                to: edge.to,
                label: edge.label,
                color: {
                    color: edge.color,
                    highlight: edge.color
                },
                width: 2,
                arrows: {
                    to: {
                        enabled: true,
                        type: 'arrow'
                    }
                },
                font: {
                    size: 12,
                    face: 'Microsoft YaHei',
                    align: 'middle'
                },
                smooth: {
                    type: 'cubicBezier',
                    roundness: 0.4
                }
            })));
            
            const data = { nodes: nodes, edges: edges };
            
            const options = {
                physics: {
                    enabled: physicsEnabled,
                    stabilization: {
                        iterations: 200
                    },
                    barnesHut: {
                        gravitationalConstant: -2000,
                        centralGravity: 0.3,
                        springLength: 200,
                        springConstant: 0.04,
                        damping: 0.09
                    }
                },
                interaction: {
                    hover: true,
                    tooltipDelay: 100,
                    zoomView: true,
                    dragView: true
                },
                nodes: {
                    borderWidth: 2,
                    shadow: {
                        enabled: true,
                        size: 10,
                        x: 5,
                        y: 5
                    }
                },
                edges: {
                    shadow: {
                        enabled: true,
                        size: 5
                    }
                }
            };
            
            network = new vis.Network(container, data, options);
            
            // 更新统计信息
            document.getElementById('node-count').textContent = graphData.nodes.length;
            document.getElementById('edge-count').textContent = graphData.edges.length;
            document.getElementById('type-count').textContent = graphData.nodeTypes.length;
            
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
        
        function togglePhysics() {
            physicsEnabled = !physicsEnabled;
            if (network) {
                network.setOptions({
                    physics: {
                        enabled: physicsEnabled
                    }
                });
            }
        }
        
        // 渲染高亮文本
        function renderHighlightedText() {
            if (!highlightedText || !highlightedText.segments) {
                document.getElementById('highlighted-text').textContent = '暂无原文内容';
                return;
            }
            
            const container = document.getElementById('highlighted-text');
            container.innerHTML = '';
            
            highlightedText.segments.forEach(segment => {
                const span = document.createElement('span');
                if (segment.type === 'entity') {
                    span.className = 'text-entity';
                    span.textContent = segment.text;
                    span.setAttribute('data-entity-id', segment.entityId);
                    span.setAttribute('data-type', segment.entityType);
                    span.style.background = `linear-gradient(120deg, ${segment.color}88 0%, ${segment.color}AA 100%)`;
                    span.onclick = () => {
                        // 点击实体时高亮图中的节点
                        if (network) {
                            network.selectNodes([segment.entityId]);
                            network.focus(segment.entityId, {
                                scale: 1.5,
                                animation: true
                            });
                        }
                    };
                } else {
                    span.className = 'text-normal';
                    span.textContent = segment.text;
                }
                container.appendChild(span);
            });
        }
        
        // 初始化
        window.addEventListener('DOMContentLoaded', function() {
            initGraph();
            renderHighlightedText();
        });
    </script>
</body>
</html>"""
        
        # 准备数据
        graph_data_json = json.dumps(graph_data, ensure_ascii=False, indent=2)
        
        # 准备高亮文本
        if highlighted_text:
            highlighted_text_html = ""
            for segment in highlighted_text["segments"]:
                # HTML转义文本内容
                escaped_text = html.escape(segment["text"])
                if segment["type"] == "entity":
                    entity_id = html.escape(str(segment["entityId"]))
                    entity_type = html.escape(str(segment["entityType"]))
                    color = html.escape(str(segment["color"]))
                    highlighted_text_html += f'<span class="text-entity" data-entity-id="{entity_id}" data-type="{entity_type}" style="background: linear-gradient(120deg, {color}88 0%, {color}AA 100%);">{escaped_text}</span>'
                else:
                    highlighted_text_html += f'<span class="text-normal">{escaped_text}</span>'
        else:
            highlighted_text_html = '<span class="text-normal">暂无原文内容</span>'
        
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

