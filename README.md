# 空地智能体系统

一个基于 **Plan-to-Execute** 架构的智能地理空间分析智能体系统，专门用于军事单位部署选址等复杂地理空间分析任务。系统融合了 **RAG增强决策**、**ReAct执行架构** 和 **自适应规划** 等先进AI技术，能够理解自然语言任务、自动规划执行流程、智能调用工具并持续优化策略。

## 🎯 智能体核心能力

### 1. **自然语言理解与任务规划**
- 理解用户自然语言描述的地理空间分析需求
- 基于RAG检索历史任务和领域知识，生成合理的执行计划
- 支持多步骤复杂任务的自动分解和排序
- **多任务拆分**：自动识别多个单位任务（如"无人机和步兵分别应该部署在哪"），为每个单位生成独立的部署计划

### 2. **RAG增强的智能决策（混合检索系统）**
- **智能路由**：根据查询内容自动路由到合适的collection（knowledge/equipment/executions）
- **混合检索**：向量语义检索 + 关键词匹配，提升专有名词和参数值的匹配准确度
- **距离阈值过滤**：使用cosine距离阈值（max_distance=0.35，相当于相似度≥0.65）确保检索质量
- **元数据加权**：unit/type/tool匹配时自动加分，强化规则约束
- **多库并查**：支持同时从多个collection检索并融合排序
- **动态top_k**：自适应召回策略，过滤后不足时自动放宽阈值（可配置增量）
- **集合启用控制**：可通过配置控制是否启用tasks和executions集合检索
- **知识库检索**：从knowledge集合检索军事单位部署规则
- **历史经验学习**：从tasks集合检索相似历史任务和计划（可配置启用/禁用）
- **执行记录参考**：从executions集合检索历史执行记录，避免重复错误（可配置启用/禁用）
- **装备信息融合**：检索装备射程等信息，优化缓冲区距离等参数

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
│       │  - 动态上下文(RAG检索)                          │
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
│  - OSM地理数据  - DEM高程数据  - WorldCover植被数据  - ChromaDB向量数据库 │
└─────────────────────────────────────────────────────────┘
```

### Plan-to-Execute 架构流程

```
用户任务输入
    │
    ▼
┌─────────────┐
│  Plan阶段   │ ◄── RAG检索: knowledge + tasks + equipment
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
- **动态上下文**：ChromaDB向量数据库，支持混合检索（向量+关键词）
  - `tasks`集合：历史任务和计划（可通过配置启用/禁用）
  - `executions`集合：执行记录和结果（最多保留30条，按时间自动清理，可通过配置启用/禁用）
  - `knowledge`集合：领域知识（15种军事单位部署规则）
  - `equipment`集合：装备信息（含射程等）
- **RAG检索优化**：
  - **Embedding模型**：BAAI/bge-large-zh-v1.5（中文优化）
  - **距离度量**：统一使用cosine距离，确保阈值可解释
  - **BGE前缀优化**：query添加"query: "前缀，passage添加"passage: "前缀
  - **智能路由**：根据关键词自动选择collection（如"射程"→equipment，"部署"→knowledge）
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
    └── dynamic/             # 动态上下文（RAG）
        └── chroma_db/       # ChromaDB向量数据库
```

## 🔄 关键设计改进

### RAG检索系统优化

**统一相似度口径**：
- 所有collection统一使用cosine距离度量
- 距离阈值 `max_distance=0.35` 相当于相似度≥0.65
- 确保阈值可解释、可调、稳定

**混合检索策略**：
- **向量语义检索**：使用BGE-large-zh-v1.5模型，query和passage分别添加前缀优化
- **关键词匹配**：提取中文词块、数字、工具名、单位名，计算匹配分数
- **融合打分**：`final_score = 0.75 * semantic_score + 0.25 * keyword_score + metadata_boost`
- **元数据加权**：unit/type/tool匹配时自动加分，强化规则约束

**智能路由机制**：
- 根据查询关键词自动路由到合适的collection
- 支持多库并查（如同时查询knowledge和equipment）
- 路由规则：
  - "射程"/"最大射程" → equipment
  - "部署"/"配置"/单位名 → knowledge
  - "工具"/"筛选" → executions

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
├─ RAG智能路由 → 根据查询内容路由到knowledge/equipment集合
├─ 混合检索knowledge集合 → 向量+关键词匹配，找到部署规则
│  ├─ 向量检索：语义相似度匹配
│  ├─ 关键词匹配：识别单位名、"部署"等关键词
│  ├─ 元数据加权：unit匹配加分（权重0.35）
│  └─ 规则：距离居民区100-300米，中等高程，缓坡
├─ 混合检索equipment集合 → 找到相关装备信息（含射程）
├─ 距离阈值过滤 → 只保留相似度≥0.65的结果
├─ 动态获取工具schema → 了解每个工具的参数结构
└─ 生成计划：
   - 单任务模式：{"goal": "...", "steps": [...]}
   - 多任务模式：{"goal": "...", "sub_plans": [{"unit": "步兵", "steps": [...]}, ...]}
```
   {
     "goal": "为步兵寻找合适的部署位置",
     "steps": [
       {
         "step_id": 1,
         "description": "筛选距离建筑和道路100-300米的区域",
         "type": "buffer",
         "params": {"buffer_distance": 200}
       },
       {
         "step_id": 2,
         "description": "筛选中等高程区域",
         "type": "elevation",
         "params": {"min_elev": 100, "max_elev": 500}
       },
       {
         "step_id": 3,
         "description": "筛选缓坡或平缓地形",
         "type": "slope",
         "params": {"max_slope": 15}
       }
     ],
     "estimated_steps": 3
   }
   
   多任务模式示例：
   {
     "goal": "为无人机和步兵分别寻找合适的部署位置",
     "sub_plans": [
       {
         "unit": "步兵",
         "steps": [
           {"step_id": 1, "type": "buffer", "params": {"buffer_distance": 200}},
           {"step_id": 2, "type": "elevation", "params": {"min_elev": 100, "max_elev": 500}}
         ]
       },
       {
         "unit": "无人机",
         "steps": [
           {"step_id": 1, "type": "buffer", "params": {"buffer_distance": 400}},
           {"step_id": 2, "type": "slope", "params": {"max_slope": 15}}
         ]
       }
     ]
   }
```

**2. 用户审查（可选）**
```
用户反馈："缓冲区距离改为200-400米"
智能体行为：
└─ Replan阶段 → 根据反馈调整计划
```

**3. Work阶段（执行）**
```
智能体行为：
├─ Step 1: 直接使用计划中的params
│  └─ type="buffer" → buffer_filter_tool
│  └─ params={"buffer_distance": 200} → 直接调用
├─ Step 2: 直接使用计划中的params
│  └─ type="elevation" → elevation_filter_tool
│  └─ params={"min_elev": 100, "max_elev": 500}
│  └─ input_geojson_path自动填充（Step1的输出）
├─ Step 3: 直接使用计划中的params
│  └─ type="slope" → slope_filter_tool
│  └─ params={"max_slope": 15}
│  └─ input_geojson_path自动填充（Step2的输出）
└─ 所有步骤直接执行，无需重新推断参数
```

**4. 结果输出**
```
GeoJSON文件保存到result目录
前端显示地图和统计信息
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

### ChromaDB配置

- 数据库路径: `AIgen/context/dynamic/chroma_db/`
- 集合: `tasks`, `executions`, `knowledge`, `equipment`
- **嵌入模型**: `BAAI/bge-large-zh-v1.5`（中文优化的大模型）
- **距离度量**: cosine（统一配置，确保阈值可解释）
- **RAG配置**:
  - `top_k=2`: 最终返回的top_k结果数
  - `oversample=2`: 向量召回时先召回 `top_k * oversample` 条候选
  - `min_k=2`: 过滤后最少保留的结果数，不足时触发降级策略
  - `max_distance=0.35`: cosine距离阈值（相当于相似度≥0.65）
  - `relaxed_distance_increment=0.5`: 降级策略中放宽阈值的增量
  - `w_sem=0.75`: 语义相似度权重（融合打分用）
  - `w_kw=0.25`: 关键词匹配权重（融合打分用）
  - `metadata_boost_unit=0.35`: unit匹配时的metadata加分
  - `metadata_boost_type=0.10`: type匹配时的metadata加分
  - `enable_tasks_collection=False`: 是否启用tasks集合检索（历史任务）
  - `enable_executions_collection=False`: 是否启用executions集合检索（执行记录）

## 📚 知识库管理

### Knowledge集合

存储了15种军事单位的部署规则：
- 步兵、重装步兵、机械化步兵
- 坦克、反坦克步兵
- 自行火炮、牵引火炮
- 防空部队、狙击手
- 特种部队、装甲侦察单位
- 工兵部队、后勤保障部队
- 指挥单位、无人机

每条规则包含：
- 适合的高程范围
- 坡度要求
- 与居民区的缓冲距离
- 部署策略说明

### 更新知识库

**方法1**: 前端界面
- "数据库管理"标签页 → 选择knowledge集合 → 点击"批量更新"

**方法2**: API接口
```bash
curl -X PUT "http://localhost:8000/api/knowledge/update"
```

**方法3**: 脚本
```bash
# 更新knowledge集合（军事单位部署规则）
python update_knowledge.py

# 更新equipment集合（装备信息）
python update_equipment.py
```

**注意**：
- 更新知识库后，所有文档会使用新的embedding模型重新编码
- 文档入库时自动添加"passage: "前缀（BGE优化）
- ID生成策略：`{collection}_{timestamp_ms}_{uuid8}`，避免并发冲突

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

1. **使用前端界面添加数据**：在"数据库管理"标签页手动添加
2. **使用API接口批量导入**：`POST /api/knowledge`
3. **修改代码**：
   - 修改 `context_manager.py` 中的 `_get_military_units_rules()` 方法（knowledge集合）
   - 修改 `context_manager.py` 中的 `_get_equipment_info()` 方法（equipment集合）
   - 运行 `update_knowledge.py` 或 `update_equipment.py` 更新数据库

**RAG检索调参**：
- 修改 `config.py` 中的 `RAG_CONFIG` 参数
- `max_distance`: 距离阈值（越小越严格，建议0.30-0.40）
- `w_sem`/`w_kw`: 语义和关键词权重（总和建议为1.0）
- `metadata_boost_*`: 元数据加分权重
- 查看日志了解检索效果，根据实际情况调整参数

## 🛠️ 技术栈

- **后端框架**: FastAPI
- **前端框架**: Streamlit
- **向量数据库**: ChromaDB（使用cosine距离度量）
- **嵌入模型**: BAAI/bge-large-zh-v1.5（中文优化的BGE大模型）
- **RAG检索**: 混合检索（向量语义 + 关键词匹配 + 元数据加权）
- **地理空间处理**: geopandas, shapely, rasterio
- **LLM**: 本地模型（Ollama兼容API）
- **地图可视化**: Folium

## 📝 注意事项

1. **数据文件**: 确保 `data/nj_merged.osm` 和 `data/dem.tif` 文件存在
2. **LLM服务**: 确保LLM API服务可访问（默认: http://192.168.1.200:11434）
3. **端口占用**: 确保8000和8501端口未被占用
4. **结果目录**: 系统会自动创建 `result/` 目录
5. **超时设置**: 前端API超时时间应大于LLM请求超时时间（建议240秒）

## 📄 许可证

MIT License
