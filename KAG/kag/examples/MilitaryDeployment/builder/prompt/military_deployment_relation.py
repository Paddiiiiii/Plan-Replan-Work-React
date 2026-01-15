# -*- coding: utf-8 -*-
"""
军事部署领域关系抽取Prompt
专门针对军事部署领域的关系抽取
"""
import json
from string import Template
from typing import List
from kag.interface import PromptABC


@PromptABC.register("military_deployment_relation")
class MilitaryDeploymentRelationPrompt(PromptABC):
    template_zh = """
{
    "instruction": "你是一个专业的军事部署领域关系抽取专家。请从输入的军事部署文本中提取实体之间的关系。关系应该反映军事部署中的战术关系、位置关系、指挥关系等。请重点关注：1) 军事单位的部署位置关系（如：部署在、位于、相对位置等）；2) 军事单位的指挥关系（如：指挥、属于、包含等）；3) 军事单位的装备关系（如：装备、配备等）；4) 阵地与地形的关系（如：位于、包含等）；5) 火力支援关系（如：支援、掩护等）。请以JSON格式响应，参照示例进行抽取。",
    "entity_list": $entity_list,
    "input": "$input",
    "example": {
        "input": "在现代战场上，兵种在不同战术形式下的相对位置具有明确的规定。在进攻形式下，步兵通常位于最前方，处于整个队形的最前端。坦克通常部署在步兵的后方或稍偏两侧，负责为步兵提供火力支援。炮兵通常部署在后方，位于队形的中央或偏后的位置，提供远程火力支援。通信兵则部署在指挥中心，通常位于队伍的后方或侧翼。",
        "entity_list": [
            {"name": "进攻形式", "category": "CombatForm"},
            {"name": "步兵", "category": "MilitaryUnit"},
            {"name": "坦克", "category": "MilitaryUnit"},
            {"name": "炮兵", "category": "MilitaryUnit"},
            {"name": "通信兵", "category": "MilitaryUnit"},
            {"name": "队形", "category": "Formation"},
            {"name": "最前方", "category": "RelativePosition"},
            {"name": "后方", "category": "RelativePosition"},
            {"name": "侧翼", "category": "RelativePosition"},
            {"name": "指挥中心", "category": "CommandPost"}
        ],
        "output": [
            {
                "subject": "步兵",
                "predicate": "部署在战术形式",
                "object": "进攻形式",
                "properties": {"positionType": "最前方"}
            },
            {
                "subject": "步兵",
                "predicate": "相对位置",
                "object": "最前方",
                "properties": {"relativeUnit": "队形", "description": "处于整个队形的最前端"}
            },
            {
                "subject": "步兵",
                "predicate": "所属队形",
                "object": "队形"
            },
            {
                "subject": "坦克",
                "predicate": "相对位置",
                "object": "后方",
                "properties": {"relativeUnit": "步兵", "description": "部署在步兵的后方或稍偏两侧"}
            },
            {
                "subject": "坦克",
                "predicate": "支援",
                "object": "步兵",
                "properties": {"supportType": "火力支援"}
            },
            {
                "subject": "炮兵",
                "predicate": "相对位置",
                "object": "后方",
                "properties": {"relativeUnit": "队形", "description": "位于队形的中央或偏后的位置"}
            },
            {
                "subject": "通信兵",
                "predicate": "部署在",
                "object": "指挥中心",
                "properties": {"distance": "位于队伍的后方或侧翼"}
            }
        ]
    },
    "input": "$input"
}
    """

    template_en = template_zh

    @property
    def template_variables(self) -> List[str]:
        return ["input", "entity_list"]

    def parse_response(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        if isinstance(rsp, dict) and "triples" in rsp:
            triples = rsp["triples"]
        else:
            triples = rsp

        # 转换为标准格式
        result = []
        for triple in triples:
            if isinstance(triple, list) and len(triple) >= 3:
                result.append({
                    "subject": triple[0],
                    "predicate": triple[1],
                    "object": triple[2],
                    "properties": triple[3] if len(triple) > 3 else {}
                })
            elif isinstance(triple, dict):
                result.append(triple)
        return result

