# Prompt模板修改总结

## 修改内容

已为军事部署领域创建了专门的Prompt模板，并更新了相关配置。

## 创建的Prompt文件

### 1. **military_deployment_ner.py** - 实体识别Prompt
   - 位置: `KAG/kag/examples/MilitaryDeployment/builder/prompt/military_deployment_ner.py`
   - 注册名: `military_deployment_ner`
   - 特点:
     - 专门针对军事部署领域的实体识别
     - 使用军事部署相关的示例
     - 强调识别军事单位、战术形式、相对位置、防御阵地等军事概念

### 2. **military_deployment_relation.py** - 关系抽取Prompt
   - 位置: `KAG/kag/examples/MilitaryDeployment/builder/prompt/military_deployment_relation.py`
   - 注册名: `military_deployment_relation`
   - 特点:
     - 专门针对军事部署领域的关系抽取
     - 重点关注：部署位置关系、指挥关系、装备关系、阵地与地形关系、火力支援关系
     - 使用军事部署相关的示例

### 3. **military_deployment_std.py** - 实体标准化Prompt
   - 位置: `KAG/kag/examples/MilitaryDeployment/builder/prompt/military_deployment_std.py`
   - 注册名: `military_deployment_std`
   - 特点:
     - 专门针对军事部署领域的实体标准化
     - 使用标准军事术语
     - 消除军事术语的歧义

## 修改的Prompt文件

### **knowledge_unit_ner.py** - 更新示例
   - 位置: `KAG/kag/builder/prompt/default/knowledge_unit_ner.py`
   - 修改内容:
     - 更新了template_zh的说明，强调军事部署领域
     - 更新了示例，使用军事部署相关的文本和实体
     - 示例包含：进攻形式、步兵、坦克、炮兵、航空兵、通信兵、队形、相对位置、指挥中心等

## Schema实体类型

根据你的schema定义，支持的实体类型包括：

- **MilitaryUnit** (军事单位)
- **CombatForm** (战术形式)
- **RelativePosition** (相对位置)
- **DefensePosition** (防御阵地)
- **CombatPosition** (战斗阵地)
- **TerrainFeature** (地形特征)
- **Weapon** (武器)
- **Obstacle** (障碍物)
- **ObstacleBelt** (障碍带)
- **Minefield** (地雷场)
- **UnitOrganization** (单位组织)
- **CombatTask** (战斗任务)
- **ObservationPost** (观察哨)
- **FireSupport** (火力支援)
- **DeploymentRule** (部署规则)
- **DefenseArea** (防御地域)
- **SupportPoint** (支撑点)
- **ApproachRoute** (接近路)
- **KillZone** (火力歼敌区)
- **ReferencePoint** (集火基准点)
- **FirePlan** (火力计划)
- **CommandPost** (指挥所)
- **DeploymentPattern** (部署模式)
- **Formation** (队形)

## 使用方法

### 自动使用（推荐）

前端应用会自动检测并使用军事部署专用Prompt。当你初始化抽取器时，系统会：
1. 自动导入自定义Prompt模块
2. 配置抽取器使用 `military_deployment_ner`、`military_deployment_relation`、`military_deployment_std`
3. 显示提示信息确认已加载

### 手动配置

如果你想在配置文件中手动指定，可以在 `kag_config.yaml` 中配置：

```yaml
kag_builder_pipeline:
  chain:
    extractor:
      type: schema_constraint_extractor
      llm: *openie_llm
      ner_prompt:
        type: military_deployment_ner
      relation_prompt:
        type: military_deployment_relation
      std_prompt:
        type: military_deployment_std
```

## Prompt特点

### 1. 领域专业性
- 使用军事部署领域的专业术语
- 示例都是军事部署相关的场景
- 强调军事概念的理解和识别

### 2. Schema对齐
- 严格遵循你的schema定义
- 只识别schema中定义的实体类型
- 如果实体类型不在schema中，返回空列表

### 3. 关系抽取重点
- **部署位置关系**: 部署在、位于、相对位置等
- **指挥关系**: 指挥、属于、包含等
- **装备关系**: 装备、配备等
- **阵地与地形关系**: 位于、包含等
- **火力支援关系**: 支援、掩护等

## 示例输出格式

### 实体识别输出
```json
[
    {
        "name": "步兵",
        "type": "MilitaryUnit",
        "category": "军事单位",
        "description": "地面作战的基本军事单位，通常位于队形最前端，负责冲锋和占领敌方阵地。"
    },
    {
        "name": "进攻形式",
        "type": "CombatForm",
        "category": "战术形式",
        "description": "一种战术形式，旨在突破敌人防线并迅速推进。"
    }
]
```

### 关系抽取输出
```json
[
    {
        "subject": "步兵",
        "predicate": "相对位置",
        "object": "最前方",
        "properties": {"relativeUnit": "队形", "description": "处于整个队形的最前端"}
    },
    {
        "subject": "坦克",
        "predicate": "支援",
        "object": "步兵",
        "properties": {"supportType": "火力支援"}
    }
]
```

## 注意事项

1. **Prompt注册**: 确保在项目启动时导入prompt模块，这样PromptABC才能注册这些prompt
2. **Schema更新**: 如果schema有更新，可能需要同步更新prompt中的示例
3. **测试**: 建议先用少量文本测试，确保prompt工作正常

## 文件结构

```
KAG/kag/examples/MilitaryDeployment/
├── builder/
│   └── prompt/
│       ├── __init__.py                    # Prompt模块初始化
│       ├── military_deployment_ner.py     # 实体识别Prompt
│       ├── military_deployment_relation.py # 关系抽取Prompt
│       └── military_deployment_std.py     # 实体标准化Prompt
└── kag_extraction_frontend.py            # 前端应用（已更新）
```

## 下一步

1. 重新启动前端应用
2. 初始化抽取器（会自动加载军事部署专用Prompt）
3. 测试实体识别和关系抽取功能
4. 根据实际效果调整prompt模板

