# -*- coding: utf-8 -*-
"""
军事部署领域实体标准化Prompt
专门针对军事部署领域的实体标准化
"""
import json
from typing import List
from kag.interface import PromptABC


@PromptABC.register("military_deployment_std")
class MilitaryDeploymentSTDPrompt(PromptABC):
    template_zh = """
{
    "instruction": "你是军事部署领域的实体标准化专家。请对输入的军事部署实体进行标准化处理，提供标准名称以消除歧义。对于军事单位，请使用标准编制名称；对于战术形式，请使用标准战术术语；对于位置关系，请使用标准位置描述。如果实体已经是标准名称，则保持不变。请以JSON格式响应。",
    "example": {
        "input": "在现代战场上，兵种在不同战术形式下的相对位置具有明确的规定。在进攻形式下，步兵通常位于最前方。坦克通常部署在步兵的后方。炮兵通常部署在后方。",
        "named_entities": [
            {"name": "进攻形式", "category": "CombatForm"},
            {"name": "步兵", "category": "MilitaryUnit"},
            {"name": "坦克", "category": "MilitaryUnit"},
            {"name": "炮兵", "category": "MilitaryUnit"},
            {"name": "最前方", "category": "RelativePosition"},
            {"name": "后方", "category": "RelativePosition"}
        ],
        "output": [
            {"name": "进攻形式", "category": "CombatForm", "official_name": "进攻战术"},
            {"name": "步兵", "category": "MilitaryUnit", "official_name": "步兵部队"},
            {"name": "坦克", "category": "MilitaryUnit", "official_name": "坦克部队"},
            {"name": "炮兵", "category": "MilitaryUnit", "official_name": "炮兵部队"},
            {"name": "最前方", "category": "RelativePosition", "official_name": "最前方"},
            {"name": "后方", "category": "RelativePosition", "official_name": "后方"}
        ]
    },
    "input": $input,
    "named_entities": $named_entities
}
    """

    template_en = template_zh

    @property
    def template_variables(self) -> List[str]:
        return ["input", "named_entities"]

    def parse_response(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        if isinstance(rsp, dict) and "named_entities" in rsp:
            standardized_entity = rsp["named_entities"]
        else:
            standardized_entity = rsp
        
        entities_with_offical_name = set()
        merged = []
        entities = kwargs.get("named_entities", [])

        # 统一处理不同的输入数据结构
        if "entities" in entities:
            entities = entities["entities"]
        if isinstance(entities, dict):
            _entities = []
            for category in entities:
                _e = entities[category]
                if isinstance(_e, list):
                    for _e2 in _e:
                        _entities.append({"name": _e2, "category": category})
                elif isinstance(_e, str):
                    _entities.append({"name": _e, "category": category})
            entities = _entities

        for entity in standardized_entity:
            merged.append(entity)
            entities_with_offical_name.add(entity["name"])
        
        # 处理LLM忽略的实体
        for entity in entities:
            if "name" in entity and entity["name"] not in entities_with_offical_name:
                entity["official_name"] = entity["name"]
                merged.append(entity)
        return merged

