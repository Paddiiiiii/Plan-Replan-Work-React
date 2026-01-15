# KAG 知识抽取交互式前端

## 概述

这是一个基于 Streamlit 的交互式前端应用，可以实时输入文本并进行知识抽取，展示完整的抽取过程和结果。

## 主要功能

### ✨ 核心特性

1. **实时知识抽取**
   - 输入文本后立即进行知识抽取
   - 支持实体识别、关系抽取、实体标准化、图谱构建等完整流程

2. **实时过程展示**
   - 显示每个抽取步骤的进度
   - 展示每个步骤识别的实体和关系
   - 实时更新抽取状态

3. **增强可视化**
   - 自动生成增强的可视化HTML
   - 原文高亮显示
   - 交互式知识图谱
   - 抽取过程步骤展示

4. **结果管理**
   - 查看原始数据（JSON格式）
   - 下载可视化结果
   - 保存抽取历史

## 使用方法

### 1. 启动前端

**方式一：使用启动脚本（推荐）**

Windows:
```bash
cd KAG/kag/examples/MilitaryDeployment
run_extraction_frontend.bat
```

Linux/Mac:
```bash
cd KAG/kag/examples/MilitaryDeployment
chmod +x run_extraction_frontend.sh
./run_extraction_frontend.sh
```

**方式二：直接使用 streamlit 命令**

```bash
cd KAG/kag/examples/MilitaryDeployment
python -m streamlit run kag_extraction_frontend.py
```

如果 `streamlit` 命令在 PATH 中，也可以直接使用：
```bash
streamlit run kag_extraction_frontend.py
```

**方式三：使用完整路径**

```bash
python -m streamlit run KAG/kag/examples/MilitaryDeployment/kag_extraction_frontend.py
```

⚠️ **注意**: 
- 不要直接运行 `python kag_extraction_frontend.py`，必须使用 `streamlit run` 命令！
- 如果 `streamlit` 命令无法识别，使用 `python -m streamlit run` 代替

### 2. 使用步骤

1. **初始化抽取器**
   - 在侧边栏点击"🔄 初始化抽取器"按钮
   - 等待初始化完成（首次可能需要一些时间）

2. **输入文本**
   - 在左侧文本框中输入要抽取的文本
   - 可以输入任意长度的文本

3. **开始抽取**
   - 点击"🚀 开始抽取"按钮
   - 系统会逐步执行：
     - 实体识别 (NER)
     - 实体标准化
     - 关系抽取
     - 图谱构建

4. **查看结果**
   - 查看抽取统计信息
   - 查看每个步骤的详细信息
   - 查看可视化结果
   - 下载HTML文件

## 界面说明

### 主界面布局

```
┌─────────────────────────────────────────────────────────┐
│  🧠 KAG 知识抽取系统                                      │
├──────────────┬──────────────────────────────────────────┤
│  侧边栏       │  主内容区                                  │
│  - 配置       │  - 输入文本                                │
│  - 使用说明   │  - 抽取统计                                │
│              │  - 抽取过程                                │
│              │  - 可视化结果                              │
└──────────────┴──────────────────────────────────────────┘
```

### 功能区域

1. **侧边栏**
   - 初始化抽取器按钮
   - 使用说明
   - 系统状态显示

2. **输入区域**
   - 文本输入框
   - 开始抽取按钮
   - 清空按钮

3. **统计区域**
   - 实体数量
   - 关系数量
   - 实体类型数量

4. **过程展示区域**
   - 进度条
   - 步骤详情
   - 识别的实体列表
   - 抽取的关系列表

5. **结果展示区域**
   - 增强可视化（HTML）
   - 原始数据（JSON）
   - 下载按钮

## 配置要求

### 前置条件

1. **KAG配置**
   - 确保 `kag_config.yaml` 文件存在
   - 配置文件中需要包含：
     - `openie_llm`: LLM配置
     - `kag_builder_pipeline`: 构建管道配置

2. **依赖包**
   ```bash
   pip install streamlit
   pip install kag  # KAG相关包
   ```

3. **项目结构**
   ```
   KAG/kag/examples/MilitaryDeployment/
   ├── kag_config.yaml          # KAG配置文件
   ├── kag_extraction_frontend.py  # 前端应用
   ├── schema/                  # Schema定义
   └── visualizations/          # 可视化输出目录（自动创建）
   ```

## 示例文本

### 军事部署示例

```
2024年，中国人民解放军进行了大规模军事部署。主要部署地点包括北京和上海。
东部战区作为重要组成部分，参与了此次部署行动。此次部署行动由张将军指挥，规模达到200万人。
部署的目的是加强国防力量，确保国家安全。
```

### 其他领域示例

可以根据你的Schema定义，输入相应领域的文本进行抽取。

## 故障排除

### 常见问题

1. **初始化失败**
   - 检查 `kag_config.yaml` 是否存在
   - 检查LLM配置是否正确
   - 检查网络连接（如果使用在线API）

2. **抽取失败**
   - 检查文本是否为空
   - 检查LLM API是否可用
   - 查看错误信息中的详细堆栈

3. **可视化失败**
   - 检查输出目录权限
   - 检查是否有足够的磁盘空间

### 调试模式

如果遇到问题，可以查看Streamlit的控制台输出，或者添加更多日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 技术实现

### 架构

- **前端**: Streamlit
- **后端**: KAG抽取器
- **可视化**: 增强可视化工具（vis.js）

### 数据流

```
用户输入文本
    ↓
创建Chunk对象
    ↓
调用抽取器
    ↓
逐步执行：
  - 实体识别
  - 实体标准化
  - 关系抽取
  - 图谱构建
    ↓
生成SubGraph
    ↓
生成可视化
    ↓
展示结果
```

## 扩展功能

### 未来改进

- [ ] 支持批量文本抽取
- [ ] 支持文件上传
- [ ] 添加抽取历史记录
- [ ] 支持导出多种格式（JSON、CSV等）
- [ ] 添加实体和关系的编辑功能
- [ ] 支持自定义抽取配置

## 注意事项

1. **性能考虑**
   - 长文本可能需要较长时间
   - 建议单次输入不超过5000字

2. **API限制**
   - 如果使用在线API，注意速率限制
   - 建议配置合理的超时时间

3. **数据安全**
   - 敏感数据请谨慎使用
   - 建议在本地环境运行

## 相关文档

- [增强可视化文档](./README_visualization.md)
- [KAG官方文档](https://github.com/OpenSPG/KAG)

## 许可证

遵循KAG项目的许可证。

