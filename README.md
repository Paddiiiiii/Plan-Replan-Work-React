# 空地智能体系统

一个基于 **Plan-to-Execute** 架构的智能地理空间分析智能体系统，专门用于军事单位部署选址等复杂地理空间分析任务。系统融合了 **RAG增强决策**、**ReAct执行架构** 和 **自适应规划** 等先进AI技术，能够理解自然语言任务、自动规划执行流程、智能调用工具并持续优化策略。

## 🎯 智能体核心能力

### 1. **自然语言理解与任务规划**
- 理解用户自然语言描述的地理空间分析需求
- 基于RAG检索历史任务和领域知识，生成合理的执行计划
- 支持多步骤复杂任务的自动分解和排序

### 2. **RAG增强的智能决策**
- **知识库检索**：从knowledge集合检索军事单位部署规则
- **历史经验学习**：从tasks集合检索相似历史任务和计划
- **执行记录参考**：从executions集合检索历史执行记录，避免重复错误
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
  - `tasks`集合：历史任务和计划
  - `equipment`集合：装备信息（含射程）
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
- **Fallback机制**：如果计划未提供params，才根据描述推断参数

#### 5. **ContextManager（上下文管理器）**
智能体的"记忆"系统：
- **静态上下文**：管理提示词模板（plan_prompt, replan_prompt, work_prompt, system_prompt）
- **动态上下文**：ChromaDB向量数据库，支持语义检索
  - `tasks`集合：历史任务和计划
  - `executions`集合：执行记录和结果
  - `knowledge`集合：领域知识（15种军事单位部署规则）
  - `equipment`集合：装备信息
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
  - 匹配的部署规则和装备信息
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
# 生成计划
curl -X POST "http://localhost:8000/api/plan" \
  -H "Content-Type: application/json" \
  -d '{"task": "为轻步兵寻找合适的部署位置"}'

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

**用户输入**：`"为轻步兵寻找合适的部署位置"`

**1. Plan阶段（规划）**
```
智能体行为：
├─ RAG检索knowledge集合 → 找到轻步兵部署规则
│  └─ 规则：距离居民区100-300米，中等高程，缓坡
├─ RAG检索tasks集合 → 找到相似历史任务
├─ RAG检索equipment集合 → 找到相关装备信息
├─ 动态获取工具schema → 了解每个工具的参数结构
└─ 生成计划（包含具体参数）：
   {
     "goal": "为轻步兵寻找合适的部署位置",
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
- 嵌入模型: `sentence-transformers/all-MiniLM-L6-v2`
- RAG配置: `top_k=5`, `similarity_threshold=0.7`

## 📚 知识库管理

### Knowledge集合

存储了15种军事单位的部署规则：
- 轻步兵、重装步兵、机械化步兵
- 坦克部队、反坦克步兵
- 自行火炮、牵引火炮
- 防空部队、狙击手
- 特种部队、装甲侦察单位
- 工兵部队、后勤保障部队
- 指挥单位、无人机侦察控制单元

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
python update_knowledge.py
```

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

1. 使用前端界面添加数据
2. 或使用API接口批量导入
3. 或修改 `context_manager.py` 中的 `update_knowledge_base()` 方法

## 🛠️ 技术栈

- **后端框架**: FastAPI
- **前端框架**: Streamlit
- **向量数据库**: ChromaDB
- **嵌入模型**: sentence-transformers/all-MiniLM-L6-v2
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
