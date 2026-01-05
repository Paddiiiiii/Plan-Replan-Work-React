# 空地智能体系统

一个基于 **Plan-to-Execute** 架构的智能地理空间分析智能体系统，专门用于军事单位部署选址等复杂地理空间分析任务。系统融合了 **RAG增强决策**、**ReAct执行架构** 和 **自适应规划** 等先进AI技术，能够理解自然语言任务、自动规划执行流程、智能调用工具并持续优化策略。

## 🎯 智能体核心能力

### 1. **自然语言理解与任务规划**
- 理解用户自然语言描述的地理空间分析需求
- 基于RAG检索历史任务和领域知识，生成合理的执行计划
- 支持多步骤复杂任务的自动分解和排序
- **多任务拆分**：自动识别多个单位任务（如"无人机和步兵分别应该部署在哪"），为每个单位生成独立的部署计划

### 2. **OpenSPG KAG知识增强的智能决策**
- **原生知识抽取**：基于OpenSPG SDK的Schema-Free抽取器，自动从原始文本中提取实体和关系
- **智能文本切分**：长文本自动切分为重叠的chunks，确保关系不跨chunk断裂
- **证据约束验证**：严格验证实体名称必须在原文中出现，过滤无关实体和幻觉
- **Schema类型约束**：实体和关系类型必须符合预定义Schema，确保知识图谱结构规范
- **数值字段规范化**：自动解析范围字符串（如"300-400"）为结构化数值字段
- **混合检索**：向量语义检索 + 关键词匹配，提升专有名词和参数值的匹配准确度
- **距离阈值过滤**：使用cosine距离阈值确保检索质量
- **元数据加权**：unit/type匹配时自动加分，强化规则约束
- **跨chunk去重**：自动合并重叠chunk中的重复实体和关系
- **可回放日志**：完整记录每个chunk的抽取过程，便于问题定位和调试

### 3. **自适应执行与错误恢复**
- **ReAct架构**：Think（思考）→ Act（行动）→ Observe（观察）循环
- **自动错误检测**：执行失败时自动分析原因
- **智能重新规划**：最多3次自动重试，根据执行结果动态调整计划
- **用户反馈驱动**：支持用户审查计划并提出修改意见，系统据此重新规划

### 4. **工具链式调用与数据流转**
- 自动识别工具间的依赖关系
- 前一个工具的输出自动作为下一个工具的输入
- 支持多工具串联执行（如：缓冲区筛选 → 高程筛选 → 坡度筛选）

### 5. **前后端分离的API架构**
- 所有前端操作通过RESTful API实现
- 支持多客户端接入（Web界面、命令行、其他系统）
- 完整的API文档和交互式测试界面

## 🏗️ 整体架构

### 架构层次

```
┌─────────────────────────────────────────────────────────┐
│                    前端层 (Streamlit)                     │
│  - 智能体任务流程界面  - 历史结果管理  - 数据库管理        │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/REST API
┌────────────────────▼────────────────────────────────────┐
│                  API服务层 (FastAPI)                      │
│  - 任务规划接口  - 执行接口  - 数据库管理接口             │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              智能体核心层 (Orchestrator)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Plan模块 │  │Replan模块│  │WorkAgent │             │
│  │ (规划)   │  │(重新规划)│  │(执行)    │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
│       │             │              │                    │
│       └─────────────┴──────────────┘                    │
│                    │                                    │
│       ┌────────────▼────────────┐                      │
│       │  ContextManager (上下文管理)                    │
│       │  - 静态上下文(提示词)                           │
│       │  - 动态上下文(OpenSPG KAG)                       │
│       │  - KAGAdapter (知识抽取与检索)                  │
│       │  - OpenSPGAdapter (原生抽取器)                  │
│       └────────────┬────────────┘                      │
└────────────────────┼────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                 工具执行层                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │BufferFilter  │ │ElevationFilter│ │SlopeFilter  │ │VegetationFilter││
│  │Tool          │ │Tool            │ │Tool         │ │Tool            ││
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              数据与知识层                                │
│  - OSM地理数据  - DEM高程数据  - WorldCover植被数据      │
│  - OpenSPG KAG知识图谱 (kg.json)                        │
│  - 抽取日志 (logs/extract_YYYYMMDD/)                    │
└─────────────────────────────────────────────────────────┘
```

### Plan-to-Execute 架构流程

```
用户任务输入
    │
    ▼
┌─────────────┐
│  Plan阶段   │ ◄── KAG检索: knowledge + equipment
│  (规划)     │     动态获取工具schema
│             │     生成包含具体参数的计划（type + params）
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 用户审查    │ ◄── 可选：用户提出修改意见
│  (可选)     │     查看计划详情、筛选步骤列表、LLM思考过程
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Replan阶段  │ ◄── 根据反馈或执行失败重新规划
│ (重新规划)  │     动态获取工具schema
│             │     生成包含具体参数的计划（type + params）
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Work阶段   │ ◄── 直接使用计划中的params参数
│  (执行)     │     工具链式调用（自动填充input_geojson_path）
└──────┬──────┘
       │
       ├── 成功 ──► 输出结果
       │
       └── 失败 ──► 自动Replan（最多3次）
```

## 📦 系统组件

### 核心智能体组件

#### 1. **Orchestrator（流程控制器）**
智能体的核心协调器，负责：
- 协调Plan、Replan、Work三个阶段的执行
- 管理执行循环和错误恢复机制
- 提供统一的执行接口

**关键方法**：
- `generate_plan()`: 生成初始计划
- `replan_with_feedback()`: 根据用户反馈重新规划
- `execute_plan()`: 执行计划（含自动重试）
- `execute_task()`: 完整流程（规划+执行）

#### 2. **PlanModule（规划模块）**
基于RAG的智能规划器：
- **多源RAG检索**：
  - `knowledge`集合：军事单位部署规则
  - `tasks`集合：历史任务和计划（可配置启用/禁用）
  - `equipment`集合：装备信息（含射程）
- **多任务识别与拆分**：自动识别包含多个单位的任务，为每个单位生成独立的子计划
- **具体参数规划**：为每个步骤生成包含具体筛选指标参数（params）的详细计划
- **工具schema动态获取**：自动获取工具的参数结构，确保参数准确性
- **知识融合**：将检索到的知识融入规划过程，合理推断参数值

#### 3. **ReplanModule（重新规划模块）**
自适应规划调整器：
- **失败分析**：分析执行失败原因
- **自动重规划**：根据执行结果自动调整计划（包含具体参数）
- **反馈驱动**：根据用户反馈修改计划参数
- **工具schema动态获取**：自动获取工具的参数结构
- **装备信息考虑**：重新规划时考虑装备射程等因素
- **与Plan一致**：使用相同的输出格式（type + params）

#### 4. **WorkAgent（执行智能体）**
高效执行器（简化ReAct架构）：
- **直接执行**：优先使用计划中提供的params参数，无需重新推断
- **工具映射**：根据步骤的type字段自动选择对应工具
- **参数验证**：确保参数正确性后再执行
- **工具链管理**：自动处理工具间的数据流转（input_geojson_path自动填充）
- **多任务执行**：支持多子计划独立执行，每个子计划生成独立的结果文件
- **Fallback机制**：如果计划未提供params，才根据描述推断参数

#### 5. **ContextManager（上下文管理器）**
智能体的"记忆"系统：
- **静态上下文**：管理提示词模板（plan_prompt, replan_prompt, work_prompt, system_prompt）
- **动态上下文**：OpenSPG KAG知识图谱，支持知识增强生成
  - `knowledge`集合：领域知识（军事单位部署规则）
  - `equipment`集合：装备信息（含射程等）
- **OpenSPG原生抽取流程**：
  1. **文本预处理**：将长文本切分为重叠的chunks（每chunk 4-8句，overlap 1-2句）
  2. **Schema-Free抽取**：使用OpenSPG SDK的SchemaFreeExtractor对每个chunk进行实体和关系抽取
  3. **证据验证**：验证实体名称必须在chunk文本中出现，过滤无关实体
  4. **类型约束**：验证实体类型和关系类型符合预定义Schema白名单
  5. **数值规范化**：自动解析范围字符串为结构化数值字段（min/max）
  6. **跨chunk合并**：合并所有chunk的抽取结果，去重实体和关系
  7. **日志记录**：保存每个chunk的输入、LLM响应和解析结果到日志文件
- **KAG知识图谱检索**：
  - **Embedding模型**：BAAI/bge-large-zh-v1.5（中文优化）
  - **问答模型**：qwen3:32b（本地部署，温度0.1用于抽取）
  - **距离度量**：统一使用cosine距离，确保阈值可解释
  - **BGE前缀优化**：query添加"query: "前缀，passage添加"passage: "前缀
  - **智能路由**：根据关键词自动选择实体类型
  - **混合打分**：语义相似度(75%) + 关键词匹配(25%) + 元数据加分
  - **质量过滤**：距离阈值过滤 + 动态top_k调整
  - **详细日志**：记录路由、召回、过滤、打分全过程，便于调参
- **上下文压缩**：自动处理过长上下文

### 工具系统

四个地理空间筛选工具，支持链式调用：

1. **buffer_filter_tool** - 缓冲区筛选
   - 根据建筑和道路距离筛选空地区域
   - 参数：`buffer_distance`（必需），`utm_crs`（可选）
   - 输出：GeoJSON文件

2. **elevation_filter_tool** - 高程筛选
   - 根据高程范围筛选区域
   - 参数：`input_geojson_path`（必需），`min_elev`，`max_elev`（可选）
   - 支持链式调用（使用buffer_filter的输出）

3. **slope_filter_tool** - 坡度筛选
   - 根据坡度范围筛选区域
   - 参数：`input_geojson_path`（必需），`min_slope`，`max_slope`（可选）
   - 支持链式调用（使用前序工具的输出）

4. **vegetation_filter_tool** - 植被筛选
   - 根据植被类型筛选区域（基于ESA WorldCover 2020数据）
   - 参数：`input_geojson_path`（必需），`vegetation_types`（可选，数组），`exclude_types`（可选，数组）
   - 支持11种土地覆盖类型：树(10)、灌木(20)、草地(30)、耕地(40)、建筑(50)、裸地/稀疏植被(60)、雪/冰(70)、水体(80)、湿地(90)、苔原(95)、永久性水体(100)
   - 支持链式调用（使用前序工具的输出）

### API服务层

**FastAPI后端**提供14个RESTful接口：

**智能体任务接口**：
- `POST /api/plan` - 生成计划
- `POST /api/replan` - 根据反馈重新规划
- `POST /api/execute` - 执行计划
- `POST /api/task` - 完整流程（规划+执行）
- `GET /api/tools` - 获取工具列表

**结果文件管理接口**：
- `GET /api/results` - 获取结果文件列表
- `GET /api/results/{filename}` - 获取结果文件内容

**数据库管理接口**：
- `GET /api/collections` - 获取所有集合信息
- `GET /api/knowledge` - 获取集合数据
- `POST /api/knowledge` - 添加数据
- `DELETE /api/knowledge/{id}` - 删除记录
- `PUT /api/knowledge/update` - 批量更新knowledge集合

### 前端界面

**Streamlit Web界面**，包含4个功能模块：
- **智能体任务**：完整的任务流程（输入→规划→审查→执行）
  - 计划详情：显示完整的计划JSON
  - LLM思考过程：仅显示思考部分（不含JSON）
  - 筛选步骤列表：显示每个步骤的类型、描述和具体参数
    - 单任务模式：显示统一的步骤列表
    - 多任务模式：按子任务分组显示，每个单位独立展示
  - 匹配的部署规则和装备信息
  - 结果展示：单任务显示单个地图，多任务使用标签页展示不同单位的结果
- **历史结果**：查看和管理历史执行结果
- **数据库管理**：管理知识库、任务历史、执行记录
- **API接口文档**：完整的API使用说明

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install fastapi uvicorn streamlit
pip install chromadb sentence-transformers
pip install geopandas shapely rasterio pyproj
pip install folium requests
```

### 2. 启动系统

```bash
cd AIgen
python main.py
```

这将同时启动：
- **后端API服务**: http://localhost:8000
- **前端界面**: http://localhost:8501
- **API文档**: http://localhost:8000/docs

### 3. 使用示例

#### 通过前端界面

1. 打开浏览器访问 http://localhost:8501
2. 在"智能体任务"标签页输入任务：
   ```
   为轻步兵寻找合适的部署位置
   ```
3. 系统将自动：
   - 检索轻步兵部署规则
   - 生成执行计划
   - 等待您审查和确认
   - 执行计划并输出结果

#### 通过API接口

```bash
# 生成计划（单任务）
curl -X POST "http://localhost:8000/api/plan" \
  -H "Content-Type: application/json" \
  -d '{"task": "为步兵寻找合适的部署位置"}'

# 生成计划（多任务）
curl -X POST "http://localhost:8000/api/plan" \
  -H "Content-Type: application/json" \
  -d '{"task": "帮我看看无人机和步兵分别应该部署在哪"}'

# 执行计划
curl -X POST "http://localhost:8000/api/execute" \
  -H "Content-Type: application/json" \
  -d '{"plan": {...}}'
```

## 📁 目录结构

```
AIgen/
├── orchestrator.py          # 流程控制器（智能体核心）
├── plan.py                  # 规划模块（RAG增强）
├── replan.py                # 重新规划模块（自适应）
├── context_manager.py       # 上下文管理（静态+动态RAG）
├── config.py                # 配置（LLM、路径、ChromaDB等）
├── main.py                  # 主入口（启动前后端）
├── api_server.py            # FastAPI后端服务
├── frontend.py              # Streamlit前端界面
├── update_knowledge.py      # 知识库更新脚本
├── work/
│   ├── agent.py             # 执行智能体（直接使用计划参数）
│   └── tools/               # 工具集合
│       ├── base_tool.py     # 工具基类
│       ├── buffer_filter_tool.py
│       ├── elevation_filter_tool.py
│       ├── slope_filter_tool.py
│       └── vegetation_filter_tool.py
├── data/                    # 数据目录
│   ├── nj_merged.osm        # OSM地理数据
│   ├── dem.tif              # DEM高程数据
│   └── WorldCover_*.tif     # ESA WorldCover植被数据
├── result/                  # 结果输出目录
└── context/                 # 上下文存储
    ├── static/              # 静态上下文（提示词）
    │   └── prompts.json
    ├── dynamic/             # 动态上下文（KAG）
    │   └── kag_storage/     # OpenSPG KAG知识图谱
    │       ├── kg.json      # 知识图谱数据（实体、关系、向量）
    │       └── logs/        # 抽取日志
    │           └── extract_YYYYMMDD/
    └── kag/                 # KAG适配器
        ├── kag_adapter.py   # KAG适配器（文本切分、证据验证、去重）
        ├── openspg_adapter.py # OpenSPG原生抽取器
        ├── openspg_schema.py  # OpenSPG Schema定义
        └── schema.py         # 旧Schema映射
```

## 🔄 关键设计改进

### OpenSPG KAG知识抽取流程

**文本预处理与切分**：
- 按句号、分号、换行符等标点符号切分文本
- 合并为每chunk 4-8句，overlap 1-2句，避免关系跨chunk断裂
- 记录每个chunk在原文中的位置（start_pos, end_pos）

**OpenSPG原生抽取**：
- 使用OpenSPG SDK的`SchemaFreeExtractor`进行实体和关系抽取
- 对每个chunk分别调用抽取器，获得实体列表和关系三元组
- LLM温度设置为0.1，提高抽取稳定性和准确性

**证据约束验证**：
- 验证实体名称必须在chunk文本中出现（支持部分匹配，至少3个字符）
- 过滤占位符、示例实体（如"实体名称"、"马云"、"乔布斯"等）
- 清理实体属性，移除OpenSPG内部字段，截断过长的文本属性

**Schema类型约束**：
- 实体类型白名单：`OperationalUnit`, `CapabilityProfile`, `DeploymentConstraint`, `PlaceFeature`
- 关系类型白名单：`hasCapability`, `hasDeploymentConstraint`, `suitableOn`, `constraintRefersTo`
- 在prompt中明确要求使用这些类型，写入前再次过滤

**数值字段规范化**：
- 自动解析范围字符串（如"300-400"）拆分为`min`/`max`字段
- 处理单值数字（如"800"）映射到对应字段
- 支持射程、缓冲距离等字段的自动解析

**跨chunk合并与去重**：
- 实体去重：使用`(normalized_name, category)`作为key
- 关系去重：使用`(source, relation_type, target)`作为key
- 标准化实体名称（去空格、统一大小写等）

**可回放日志**：
- 保存每个chunk的输入文本、LLM原始响应、解析后的实体和关系
- 记录最终合并后的实体和关系列表
- 日志文件保存在`kg_storage_path/logs/extract_YYYYMMDD/`目录

### KAG检索系统优化

**统一相似度口径**：
- 所有collection统一使用cosine距离度量
- 距离阈值 `max_distance=0.35` 相当于相似度≥0.65
- 确保阈值可解释、可调、稳定

**混合检索策略**：
- **向量语义检索**：使用BGE-large-zh-v1.5模型，query和passage分别添加前缀优化
- **关键词匹配**：提取中文词块、数字、工具名、单位名，计算匹配分数
- **融合打分**：`final_score = 0.75 * semantic_score + 0.25 * keyword_score + metadata_boost`
- **元数据加权**：unit/type匹配时自动加分，强化规则约束

**智能路由机制**：
- 根据查询关键词自动路由到合适的collection
- 支持多库并查（如同时查询knowledge和equipment）
- 路由规则：
  - "射程"/"最大射程" → equipment
  - "部署"/"配置"/单位名 → knowledge

**质量保证机制**：
- **距离阈值过滤**：只保留 `distance <= max_distance` 的结果
- **动态top_k**：先召回 `top_k * oversample` 条，过滤后不足 `min_k` 时放宽阈值（增量可配置）
- **低置信度标记**：放宽阈值的结果标记为 `low_confidence=True`

**详细日志记录**：
- 记录路由信息、关键词提取、召回数量、过滤前后数量
- 记录每个候选的distance、semantic_score、keyword_score、metadata_boost、final_score
- 便于调参和问题诊断

### 职能分离优化

**Plan阶段（规划）**：
- 负责理解任务需求
- 检索相关知识和历史经验
- **为每个步骤确定具体的筛选指标参数**
- 动态获取工具schema确保参数准确性
- 输出格式：`{type, description, params}`

**Work阶段（执行）**：
- **直接使用计划中的params参数**，无需重新推断
- 根据type字段自动映射到对应工具
- 自动处理工具间的数据流转
- 仅在计划未提供params时才推断参数

**Replan阶段（重新规划）**：
- 与Plan阶段使用相同的输出格式
- 根据反馈或执行失败调整参数值
- 动态获取工具schema确保参数准确性

### 工具Schema动态获取

- Plan和Replan模块都会动态获取工具的实际schema
- 确保LLM了解每个工具的参数类型、描述和要求
- 提高参数生成的准确性和一致性

## 🧠 智能体工作流程示例

### 完整任务执行流程

**用户输入**：`"为步兵寻找合适的部署位置"` 或 `"帮我看看无人机和步兵分别应该部署在哪"`

**1. Plan阶段（规划）**
```
智能体行为：
├─ 任务识别 → 判断是单任务还是多任务模式
├─ KAG智能路由 → 根据查询内容路由到knowledge/equipment集合
├─ 混合检索knowledge集合 → 向量+关键词匹配，找到部署规则
│  ├─ 向量检索：语义相似度匹配
│  ├─ 关键词匹配：识别单位名、"部署"等关键词
│  ├─ 元数据加权：unit匹配加分
│  └─ 从知识图谱中检索相关实体和关系
├─ 混合检索equipment集合 → 找到相关装备信息（含射程）
├─ 距离阈值过滤 → 只保留相似度≥0.65的结果
├─ 动态获取工具schema → 了解每个工具的参数结构
└─ 生成计划：
   - 单任务模式：包含goal和steps列表
   - 多任务模式：包含goal和sub_plans列表，每个子计划对应一个单位
   - 每个步骤包含type、description和params（具体参数值）
```

**2. 用户审查（可选）**
```
用户反馈：提出修改意见（如"缓冲区距离改为200-400米"）
智能体行为：
└─ Replan阶段 → 根据反馈调整计划参数
```

**3. Work阶段（执行）**
```
智能体行为：
├─ 多任务识别 → 判断是否有sub_plans
├─ 单任务执行流程：
│  ├─ Step 1: 直接使用计划中的params
│  │  └─ type="buffer" → buffer_filter_tool
│  │  └─ params直接传递给工具执行
│  ├─ Step 2: 直接使用计划中的params
│  │  └─ type="elevation" → elevation_filter_tool
│  │  └─ input_geojson_path自动填充（Step1的输出）
│  └─ 后续步骤：链式调用，自动传递中间结果
└─ 多任务执行流程：
   ├─ 为每个sub_plan独立执行
   ├─ 每个子计划从初始输入开始
   └─ 生成独立的结果文件
```

**4. 结果输出**
```
单任务模式：生成单个GeoJSON文件，前端显示单个地图
多任务模式：生成多个GeoJSON文件，前端使用标签页展示不同单位的结果
```

### 错误恢复机制

如果执行失败：
```
执行失败
    │
    ▼
分析失败原因（ReplanModule）
    │
    ▼
重新规划（最多3次）
    │
    ▼
重新执行
```

## ⚙️ 配置说明

### LLM配置（config.py）

```python
LLM_CONFIG = {
    "api_endpoint": "http://192.168.1.200:11434/v1/chat/completions",
    "model": "qwen3:32b",
    "temperature": 0.7,
    "max_tokens": 4096,
    "timeout": 180
}
```

### 数据路径

- OSM文件: `AIgen/data/nj_merged.osm`
- DEM文件: `AIgen/data/dem.tif`
- 结果目录: `AIgen/result/`

### OpenSPG KAG配置

- **知识图谱存储路径**: `AIgen/context/dynamic/kag_storage/`
- **抽取日志路径**: `kg_storage_path/logs/extract_YYYYMMDD/`
- **实体类型Schema**: `OperationalUnit`, `CapabilityProfile`, `DeploymentConstraint`, `PlaceFeature`
- **关系类型Schema**: `hasCapability`, `hasDeploymentConstraint`, `suitableOn`, `constraintRefersTo`
- **嵌入模型**: `BAAI/bge-large-zh-v1.5`（中文优化的大模型）
- **问答模型**: `qwen3:32b`（本地部署，通过LLM_CONFIG配置）
- **抽取温度**: `0.1`（降低幻觉，提高稳定性）
- **文本切分参数**:
  - `chunk_size=6`: 每个chunk包含的句子数
  - `overlap=2`: chunk之间的重叠句子数
- **距离度量**: cosine（统一配置，确保阈值可解释）
- **KAG检索配置**:
  - `top_k=2`: 最终返回的top_k结果数
  - `oversample=2`: 向量召回时先召回 `top_k * oversample` 条候选
  - `min_k=2`: 过滤后最少保留的结果数，不足时触发降级策略
  - `max_distance=0.35`: cosine距离阈值（相当于相似度≥0.65）
  - `relaxed_distance_increment=0.5`: 降级策略中放宽阈值的增量
  - `w_sem=0.75`: 语义相似度权重（融合打分用）
  - `w_kw=0.25`: 关键词匹配权重（融合打分用）
  - `metadata_boost_unit=0.35`: unit匹配时的metadata加分
  - `metadata_boost_type=0.10`: type匹配时的metadata加分

## 📚 知识库管理

### 知识抽取流程

系统使用OpenSPG SDK的原生抽取能力，从原始文本中自动提取结构化知识：

1. **文本输入**：提供整段文本（不包含预定义结构）
2. **自动切分**：系统自动将长文本切分为重叠的chunks
3. **实体抽取**：对每个chunk使用OpenSPG SchemaFreeExtractor抽取实体
4. **关系抽取**：从实体间提取符合Schema的关系三元组
5. **证据验证**：验证实体名称必须在原文中出现
6. **类型约束**：确保实体和关系类型符合预定义Schema
7. **数值规范化**：自动解析范围字符串为结构化数值
8. **跨chunk合并**：合并所有chunk的结果，去重实体和关系
9. **持久化存储**：保存到知识图谱文件（kg.json）

### 更新知识库

**方法1**: 脚本更新（推荐）
```bash
# 更新knowledge集合（军事单位部署规则）
python update_knowledge.py

# 更新equipment集合（装备信息）
python update_equipment.py
```

**方法2**: 前端界面
- "数据库管理"标签页 → 选择集合 → 点击"批量更新"

**方法3**: API接口
```bash
curl -X PUT "http://localhost:8000/api/knowledge/update"
```

### 查看知识图谱

**方法1**: 查看脚本
```bash
python view_kag.py              # 查看所有信息
python view_kag.py --entities   # 只查看实体
python view_kag.py --relations  # 只查看关系
python view_kag.py --summary    # 只查看摘要
```

**方法2**: API接口
```bash
curl "http://localhost:8000/api/knowledge?collection=knowledge"
curl "http://localhost:8000/api/collections"
```

**方法3**: 直接查看文件
- 知识图谱：`context/dynamic/kag_storage/kg.json`
- 抽取日志：`context/dynamic/kag_storage/logs/extract_YYYYMMDD/`

### 抽取日志分析

系统为每次抽取操作生成完整的日志文件，包含：
- 输入文本预览和长度
- 每个chunk的文本、位置、抽取结果
- LLM原始响应（NER、标准化、三元组）
- 最终合并后的实体和关系列表

通过日志可以：
- 定位无关实体的来源（是LLM生成还是后处理误放行）
- 分析chunk切分效果
- 调试抽取参数和prompt效果

## 🔧 开发指南

### 添加新工具

1. 在 `work/tools/` 目录创建新工具文件
2. 继承 `BaseTool` 类
3. 实现 `execute()` 和 `validate_params()` 方法
4. 在 `work/agent.py` 中注册工具

### 修改提示词

1. 直接编辑 `context/static/prompts.json`
   - `plan_prompt`: 规划阶段的提示词（要求生成包含具体参数的步骤）
   - `replan_prompt`: 重新规划阶段的提示词（与plan_prompt格式一致）
   - `work_prompt`: 执行阶段的提示词（直接使用计划中的params）
   - `system_prompt`: 系统级提示词
2. 系统会在启动时自动加载最新提示词
3. **注意**：如果 `prompts.json` 不存在，系统会抛出错误提示创建文件

### 扩展知识库

1. **修改更新脚本**：
   - 修改 `update_knowledge.py` 中的 `get_military_units_rules()` 函数，提供新的文本内容
   - 修改 `update_equipment.py` 中的 `get_equipment_info()` 函数，提供新的文本内容
   - 运行对应脚本，系统会自动抽取实体和关系

2. **使用前端界面**：在"数据库管理"标签页手动添加文本，系统会自动抽取

3. **使用API接口**：`POST /api/knowledge` 批量导入文本

**知识抽取调参**：
- 修改 `config.py` 中的 `KAG_CONFIG` 参数
- `chunk_size`: chunk大小（建议4-8句）
- `overlap`: chunk重叠（建议1-2句）
- 修改 `openspg_adapter.py` 中的prompt模板优化抽取效果
- 查看抽取日志分析效果，根据实际情况调整参数

**KAG检索调参**：
- 修改 `config.py` 中的 `KAG_CONFIG` 参数
- `max_distance`: 距离阈值（越小越严格，建议0.30-0.40）
- `w_sem`/`w_kw`: 语义和关键词权重（总和建议为1.0）
- `metadata_boost_*`: 元数据加分权重
- 查看日志了解检索效果，根据实际情况调整参数

## 🛠️ 技术栈

- **后端框架**: FastAPI
- **前端框架**: Streamlit
- **知识图谱**: OpenSPG KAG SDK（原生Schema-Free抽取）
- **嵌入模型**: BAAI/bge-large-zh-v1.5（中文优化的BGE大模型）
- **知识抽取**: OpenSPG SchemaFreeExtractor（文本切分 + 证据验证 + Schema约束）
- **知识检索**: 混合检索（向量语义 + 关键词匹配 + 元数据加权）
- **地理空间处理**: geopandas, shapely, rasterio
- **LLM**: 本地模型（Ollama兼容API，温度0.1用于抽取）
- **地图可视化**: Folium

## 📝 注意事项

1. **数据文件**: 确保 `data/nj_merged.osm` 和 `data/dem.tif` 文件存在
2. **LLM服务**: 确保LLM API服务可访问（默认: http://192.168.1.200:11434）
3. **端口占用**: 确保8000和8501端口未被占用
4. **结果目录**: 系统会自动创建 `result/` 目录
5. **超时设置**: 前端API超时时间应大于LLM请求超时时间（建议240秒）

## 📄 许可证

MIT License
