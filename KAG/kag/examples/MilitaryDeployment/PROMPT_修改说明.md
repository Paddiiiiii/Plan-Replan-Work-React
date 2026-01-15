# Prompt 修改说明

## 问题说明

错误信息显示LLM返回的是列表（list），但解析函数期望字符串。已修复 `load_NER_data` 函数来处理这种情况。

## Prompt 位置

### 1. Schema Constraint Extractor 使用的 Prompt

`schema_constraint_extractor` 默认使用以下prompt：

- **NER Prompt**: `default_ner`
  - 文件位置: `KAG/kag/builder/prompt/default/ner.py`
  - 类名: `OpenIENERPrompt`
  - 注册名: `@PromptABC.register("default_ner")`

- **Standardization Prompt**: `default_std`
  - 文件位置: `KAG/kag/builder/prompt/default/std.py`

- **Relation Prompt**: `default_relation`
  - 文件位置: `KAG/kag/builder/prompt/default/relation.py`

### 2. Knowledge Unit Extractor 使用的 Prompt

如果使用的是 `knowledge_unit_extractor`，会使用：

- **NER Prompt**: `knowledge_unit_ner`
  - 文件位置: `KAG/kag/builder/prompt/default/knowledge_unit_ner.py`
  - 类名: `OpenIENERKnowledgeUnitPrompt`
  - 注册名: `@PromptABC.register("knowledge_unit_ner")`

## 如何修改 Prompt

### 方法1: 修改默认 Prompt（影响所有使用该prompt的地方）

编辑对应的prompt文件，例如：
- `KAG/kag/builder/prompt/default/ner.py` - 修改NER prompt
- `KAG/kag/builder/prompt/default/knowledge_unit_ner.py` - 修改knowledge_unit_ner prompt

### 方法2: 创建自定义 Prompt（推荐）

1. 在项目目录下创建自定义prompt文件，例如：
   ```
   KAG/kag/examples/MilitaryDeployment/builder/prompt/custom_ner.py
   ```

2. 创建自定义prompt类：
   ```python
   from kag.interface import PromptABC
   from kag.builder.prompt.default.ner import OpenIENERPrompt
   
   @PromptABC.register("military_deployment_ner")
   class MilitaryDeploymentNERPrompt(OpenIENERPrompt):
       template_zh = """
       你的自定义prompt模板...
       """
   ```

3. 在配置文件中指定使用自定义prompt：
   ```yaml
   extractor:
     type: schema_constraint_extractor
     llm: *openie_llm
     ner_prompt:
       type: military_deployment_ner
   ```

### 方法3: 在前端代码中指定 Prompt

修改 `kag_extraction_frontend.py` 中的extractor配置：

```python
extractor_config = {
    "type": "schema_constraint_extractor",
    "llm": extractor_config.get("llm", KAG_CONFIG.all_config.get("openie_llm", {})),
    "ner_prompt": {
        "type": "default_ner"  # 或 "knowledge_unit_ner" 或其他自定义prompt
    },
}
```

## 当前使用的 Prompt

根据错误信息，当前使用的是 `knowledge_unit_ner` prompt，定义在：
- **文件**: `KAG/kag/builder/prompt/default/knowledge_unit_ner.py`
- **模板变量**: `template_zh` (中文模板)
- **解析函数**: `parse_response` 方法调用 `load_NER_data`

## 已修复的问题

已修复 `KAG/kag/builder/prompt/default/util.py` 中的 `load_NER_data` 函数：
- 现在可以处理列表类型的响应
- 可以处理字典类型的响应
- 保持对字符串类型的兼容性

## 修改 Prompt 模板

要修改你看到的那个prompt模板，编辑：
```
KAG/kag/builder/prompt/default/knowledge_unit_ner.py
```

找到 `template_zh` 变量（大约在第97行），修改其中的模板内容。

## 注意事项

1. 修改prompt后需要重启应用才能生效
2. 如果创建自定义prompt，确保在项目启动时导入该模块
3. Prompt模板中使用 `$schema` 和 `$input` 作为变量占位符
4. 确保prompt的输出格式与解析函数期望的格式一致

