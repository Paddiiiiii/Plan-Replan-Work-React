# -*- coding: utf-8 -*-
"""
KAG 实体-关系图增强可视化示例
展示如何使用增强的可视化工具来查看抽取结果
"""
import os
import sys
from pathlib import Path

# 添加KAG根目录到路径
KAG_ROOT = Path(__file__).resolve().parents[3]
if str(KAG_ROOT) not in sys.path:
    sys.path.insert(0, str(KAG_ROOT))

from kag.builder.model.sub_graph import SubGraph, Node, Edge
from kag.builder.model.chunk import Chunk
from kag.builder.component.reader.enhanced_graph_visualizer import visualize_enhanced_graph
from kag.builder.component.reader.markdown_to_graph import visualize_graph


def create_sample_subgraph():
    """创建一个示例子图用于演示"""
    # 创建节点
    nodes = [
        Node("1", "中国人民解放军", "MilitaryUnit", {
            "name": "中国人民解放军",
            "type": "军队",
            "strength": "200万"
        }),
        Node("2", "北京", "Location", {
            "name": "北京",
            "type": "城市",
            "province": "北京市"
        }),
        Node("3", "部署", "Deployment", {
            "name": "部署",
            "time": "2024年",
            "scale": "大规模"
        }),
        Node("4", "东部战区", "MilitaryUnit", {
            "name": "东部战区",
            "type": "战区",
            "commander": "张将军"
        }),
        Node("5", "上海", "Location", {
            "name": "上海",
            "type": "城市",
            "province": "上海市"
        }),
    ]
    
    # 创建边
    edges = [
        Edge("e1", nodes[0], nodes[2], "执行", {}),
        Edge("e2", nodes[2], nodes[1], "部署地点", {}),
        Edge("e3", nodes[0], nodes[3], "包含", {}),
        Edge("e4", nodes[3], nodes[4], "部署地点", {}),
        Edge("e5", nodes[0], nodes[1], "位于", {}),
    ]
    
    return SubGraph(nodes, edges)


def create_sample_text():
    """创建示例原文"""
    return """2024年，中国人民解放军进行了大规模军事部署。主要部署地点包括北京和上海。
东部战区作为重要组成部分，参与了此次部署行动。此次部署行动由张将军指挥，规模达到200万人。
部署的目的是加强国防力量，确保国家安全。"""


def create_extraction_steps():
    """创建抽取过程步骤"""
    return [
        {
            "step": 1,
            "name": "实体识别 (NER)",
            "description": "从文本中识别出5个实体：中国人民解放军、北京、部署、东部战区、上海",
            "entities": [
                {"name": "中国人民解放军", "type": "MilitaryUnit"},
                {"name": "北京", "type": "Location"},
                {"name": "部署", "type": "Deployment"},
                {"name": "东部战区", "type": "MilitaryUnit"},
                {"name": "上海", "type": "Location"},
            ],
            "status": "completed"
        },
        {
            "step": 2,
            "name": "关系抽取",
            "description": "抽取了5条关系，包括执行、部署地点、包含、位于等关系",
            "relations": [
                {"from": "中国人民解放军", "to": "部署", "label": "执行"},
                {"from": "部署", "to": "北京", "label": "部署地点"},
                {"from": "中国人民解放军", "to": "东部战区", "label": "包含"},
                {"from": "东部战区", "to": "上海", "label": "部署地点"},
                {"from": "中国人民解放军", "to": "北京", "label": "位于"},
            ],
            "status": "completed"
        },
        {
            "step": 3,
            "name": "实体标准化",
            "description": "对识别的实体进行标准化处理，确保实体名称和类型的一致性",
            "status": "completed"
        },
        {
            "step": 4,
            "name": "图谱构建",
            "description": "构建包含5个节点和5条边的知识图谱，完成知识表示",
            "status": "completed"
        }
    ]


def main():
    """主函数"""
    print("=" * 60)
    print("KAG 实体-关系图增强可视化示例")
    print("=" * 60)
    
    # 创建示例数据
    print("\n[1/4] 创建示例数据...")
    subgraph = create_sample_subgraph()
    source_text = create_sample_text()
    extraction_steps = create_extraction_steps()
    
    print(f"   - 节点数: {len(subgraph.nodes)}")
    print(f"   - 边数: {len(subgraph.edges)}")
    print(f"   - 原文长度: {len(source_text)} 字符")
    print(f"   - 抽取步骤: {len(extraction_steps)} 步")
    
    # 创建输出目录
    output_dir = Path(__file__).parent / "visualizations"
    output_dir.mkdir(exist_ok=True)
    
    # 方法1: 使用增强可视化（推荐）
    print("\n[2/4] 生成增强可视化...")
    try:
        enhanced_output = visualize_enhanced_graph(
            subgraph=subgraph,
            source_text=source_text,
            extraction_steps=extraction_steps,
            output_path=str(output_dir / "enhanced_visualization")
        )
        print(f"   ✓ 增强可视化已保存: {enhanced_output}")
    except Exception as e:
        print(f"   ✗ 增强可视化失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 方法2: 使用标准可视化（带增强选项）
    print("\n[3/4] 生成标准可视化（增强模式）...")
    try:
        standard_enhanced_output = visualize_graph(
            subgraph=subgraph,
            output_path=str(output_dir / "standard_enhanced"),
            enhanced=True,
            source_text=source_text,
            extraction_steps=extraction_steps,
        )
        print(f"   ✓ 标准增强可视化已保存: {standard_enhanced_output}")
    except Exception as e:
        print(f"   ✗ 标准增强可视化失败: {e}")
    
    # 方法3: 使用标准可视化（传统模式）
    print("\n[4/4] 生成标准可视化（传统模式）...")
    try:
        standard_output = visualize_graph(
            subgraph=subgraph,
            output_path=str(output_dir / "standard_traditional"),
            enhanced=False,
        )
        print(f"   ✓ 标准可视化已保存: {standard_output}")
    except Exception as e:
        print(f"   ✗ 标准可视化失败: {e}")
    
    print("\n" + "=" * 60)
    print("可视化完成！")
    print("=" * 60)
    print(f"\n输出目录: {output_dir}")
    print("\n推荐使用增强可视化，它包含以下特性：")
    print("  - ✨ 原文高亮显示，点击实体可定位到图中")
    print("  - 🎯 抽取过程步骤展示")
    print("  - 🎨 炫酷的视觉效果和动画")
    print("  - 🔍 交互式知识图谱探索")
    print("  - 📊 统计信息展示")
    print("=" * 60)


if __name__ == "__main__":
    main()

