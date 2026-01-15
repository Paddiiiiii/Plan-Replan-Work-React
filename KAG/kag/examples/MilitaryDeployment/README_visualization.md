# KAG 实体-关系图增强可视化

## 概述

这是一个增强的实体-关系图可视化工具，提供了比标准可视化更丰富的功能和更炫酷的视觉效果。

## 主要特性

### ✨ 核心功能

1. **原文高亮显示**
   - 自动识别并高亮显示文本中的实体
   - 点击高亮的实体可以定位到图中的对应节点
   - 鼠标悬停显示实体类型信息

2. **抽取过程展示**
   - 展示知识抽取的完整流程
   - 包括实体识别、关系抽取、实体标准化、图谱构建等步骤
   - 每个步骤显示相关的实体和关系信息

3. **交互式知识图谱**
   - 使用 vis.js 构建的交互式网络图
   - 支持拖拽、缩放、搜索等操作
   - 节点和边的颜色根据类型自动分配

4. **炫酷的视觉效果**
   - 现代化的渐变背景和配色方案
   - 流畅的动画效果
   - 响应式设计，适配不同屏幕尺寸

## 使用方法

### 方法1: 直接使用增强可视化函数

```python
from kag.builder.component.reader.enhanced_graph_visualizer import visualize_enhanced_graph
from kag.builder.model.sub_graph import SubGraph
from kag.builder.model.chunk import Chunk

# 准备数据
subgraph = SubGraph(nodes, edges)
source_text = "你的原文内容..."
extraction_steps = [
    {
        "step": 1,
        "name": "实体识别",
        "description": "从文本中识别出X个实体",
        "entities": [...],
        "status": "completed"
    },
    # ... 更多步骤
]

# 生成可视化
output_path = visualize_enhanced_graph(
    subgraph=subgraph,
    source_text=source_text,
    extraction_steps=extraction_steps,
    output_path="my_visualization"
)
```

### 方法2: 使用标准可视化函数的增强模式

```python
from kag.builder.component.reader.markdown_to_graph import visualize_graph

# 使用增强模式
visualize_graph(
    subgraph=subgraph,
    output_path="my_visualization",
    enhanced=True,  # 启用增强模式
    source_text=source_text,
    extraction_steps=extraction_steps
)
```

### 方法3: 运行示例脚本

```bash
cd KAG/kag/examples/MilitaryDeployment
python visualize_extraction.py
```

## 参数说明

### visualize_enhanced_graph 参数

- `subgraph` (SubGraph, 必需): 要可视化的子图对象
- `source_text` (str, 可选): 原始文本内容，用于高亮显示
- `source_chunk` (Chunk, 可选): 原始Chunk对象，如果提供会自动提取文本
- `extraction_steps` (List[Dict], 可选): 抽取过程步骤列表
- `output_path` (str, 可选): 输出文件路径（不含扩展名），默认为 "enhanced_graph_visualization"

### extraction_steps 格式

每个步骤字典应包含以下字段：

```python
{
    "step": 1,  # 步骤编号
    "name": "实体识别",  # 步骤名称
    "description": "从文本中识别出X个实体",  # 步骤描述
    "entities": [  # 可选：该步骤识别的实体列表
        {"name": "实体名", "type": "实体类型"}
    ],
    "relations": [  # 可选：该步骤抽取的关系列表
        {"from": "源实体", "to": "目标实体", "label": "关系类型"}
    ],
    "status": "completed"  # 步骤状态
}
```

## 输出文件

生成的HTML文件包含：

1. **顶部统计信息**
   - 实体节点数量
   - 关系边数量
   - 实体类型数量

2. **知识图谱面板**
   - 交互式网络图
   - 控制按钮（重置视图、适应窗口、切换物理引擎）
   - 图例显示

3. **原文高亮面板**
   - 高亮显示的原文
   - 可点击的实体标记

4. **抽取过程面板**
   - 步骤化的抽取过程展示
   - 每个步骤的详细信息

## 视觉效果特点

- 🎨 **现代配色**: 使用渐变背景和现代配色方案
- ✨ **动画效果**: 流畅的过渡动画和悬停效果
- 📱 **响应式设计**: 适配不同屏幕尺寸
- 🎯 **交互式**: 支持点击、拖拽、缩放等操作
- 🌈 **颜色编码**: 不同类型的实体和关系使用不同颜色

## 技术实现

- **前端框架**: 纯HTML/CSS/JavaScript
- **图可视化**: vis.js Network
- **样式**: 现代CSS3（渐变、动画、响应式布局）
- **后端**: Python，使用html.escape确保安全性

## 注意事项

1. 生成的HTML文件需要网络连接以加载 vis.js 库（使用CDN）
2. 如果原文很长，建议分段处理以提高性能
3. 实体名称匹配使用精确匹配，确保实体名称与原文中的文本完全一致

## 示例

运行示例脚本查看完整效果：

```bash
python visualize_extraction.py
```

生成的HTML文件可以在浏览器中打开查看。

## 未来改进

- [ ] 支持更多可视化布局算法
- [ ] 添加导出功能（PNG、SVG等）
- [ ] 支持自定义主题
- [ ] 添加搜索和过滤功能
- [ ] 支持时间线动画展示抽取过程

