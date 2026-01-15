# -*- coding: utf-8 -*-
"""
军事部署领域实体识别Prompt
专门针对军事部署领域的实体抽取
"""
import json
from string import Template
from typing import List
from kag.interface import PromptABC
from knext.schema.client import SchemaClient
from knext.schema.model.base import SpgTypeEnum


@PromptABC.register("military_deployment_ner")
class MilitaryDeploymentNERPrompt(PromptABC):
    template_zh = """
{
    "instruction": "你是一个专业的军事部署领域实体识别专家。请从输入的军事部署文本中提取所有与军事部署相关的实体。实体必须严格符合schema中定义的军事部署实体类型。如果文本中没有对应类型的实体，请返回空列表。请以JSON格式响应，参照示例进行抽取。",
    "schema": $schema,
    "example": {
        "input": "在现代战场上，兵种在不同战术形式下的相对位置具有明确的规定，以确保各兵种的最大战术效能。在进攻形式下，兵种部署的目的是突破敌人防线并迅速推进。步兵通常位于最前方，处于整个队形的最前端，直接向敌人阵地推进，承担冲锋和占领敌方阵地的任务。紧随步兵之后的是坦克，通常部署在步兵的后方或稍偏两侧，负责为步兵提供火力支援并突破敌方的防线。炮兵通常部署在后方，位于队形的中央或偏后的位置，提供远程火力支援，用于打击敌方的阵地和重武器。航空兵则位于空中，通常处于整个战场的上空，提供空中打击和侦察，压制敌方空防并摧毁敌方后方的补给线和指挥设施。通信兵则部署在指挥中心，通常位于队伍的后方或侧翼，确保前线部队与指挥中心之间的信息传递流畅，保证指挥系统的有效运作。",
        "output": [
            {
                "name": "进攻形式",
                "type": "CombatForm",
                "category": "战术形式",
                "description": "一种战术形式，旨在突破敌人防线并迅速推进，以实现战场上的优势。"
            },
            {
                "name": "步兵",
                "type": "MilitaryUnit",
                "category": "军事单位",
                "description": "地面作战的基本军事单位，通常位于队形最前端，负责冲锋和占领敌方阵地。"
            },
            {
                "name": "坦克",
                "type": "MilitaryUnit",
                "category": "军事单位",
                "description": "装甲军事单位，通常部署在步兵后方或两侧，提供火力支援并突破敌方防线。"
            },
            {
                "name": "炮兵",
                "type": "MilitaryUnit",
                "category": "军事单位",
                "description": "远程火力支援军事单位，通常部署在后方，用于打击敌方阵地和重武器。"
            },
            {
                "name": "航空兵",
                "type": "MilitaryUnit",
                "category": "军事单位",
                "description": "空中作战军事单位，通常位于战场上空，提供空中打击、侦察和压制敌方空防。"
            },
            {
                "name": "通信兵",
                "type": "MilitaryUnit",
                "category": "军事单位",
                "description": "负责信息传递的军事单位，通常部署在指挥中心附近，确保前线与指挥系统之间的通信流畅。"
            },
            {
                "name": "队形",
                "type": "Formation",
                "category": "队形",
                "description": "部队在战场上的排列和部署结构，用于优化战术效能和协调各兵种行动。"
            },
            {
                "name": "最前方",
                "type": "RelativePosition",
                "category": "相对位置",
                "description": "位于整个队形最前端的相对位置，通常由步兵占据。"
            },
            {
                "name": "后方",
                "type": "RelativePosition",
                "category": "相对位置",
                "description": "位于队形后方的相对位置，通常部署炮兵等支援单位。"
            },
            {
                "name": "侧翼",
                "type": "RelativePosition",
                "category": "相对位置",
                "description": "位于队伍侧翼的相对位置，通常部署通信兵等辅助单位。"
            },
            {
                "name": "指挥中心",
                "type": "CommandPost",
                "category": "指挥所",
                "description": "战场上的指挥设施，通常位于后方或侧翼，负责协调部队行动和决策。"
            },
            {
                "name": "敌方阵地",
                "type": "DefensePosition",
                "category": "防御阵地",
                "description": "敌人部署的防御设施，通常包括工事和火力点，用于抵抗进攻。"
            }
        ]
    },
    "input": "$input"
}
    """

    template_en = template_zh

    def __init__(self, language: str = "", **kwargs):
        super().__init__(language, **kwargs)
        project_schema = SchemaClient(
            host_addr=self.kag_project_config.host_addr,
            project_id=self.kag_project_config.project_id,
        ).load()
        self.schema = []
        for name, value in project_schema.items():
            # 过滤掉索引类型和系统类型
            if value.spg_type_enum != SpgTypeEnum.Index:
                # 排除系统类型
                if name not in ["Chunk", "AtomicQuery", "KnowledgeUnit", "Summary", "Outline", "Doc"]:
                    self.schema.append(name)

        self.template = Template(self.template).safe_substitute(
            schema=json.dumps(self.schema, ensure_ascii=False)
        )

    @property
    def template_variables(self) -> List[str]:
        return ["input"]

    def parse_response(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        if isinstance(rsp, dict) and "named_entities" in rsp:
            entities = rsp["named_entities"]
        else:
            entities = rsp

        # 转换为标准格式
        result = []
        for entity in entities:
            if isinstance(entity, dict):
                # 确保有name和category字段
                if "name" in entity and "category" in entity:
                    result.append({
                        "name": entity["name"],
                        "category": entity.get("category", entity.get("type", "")),
                        "properties": entity.get("properties", {})
                    })
        return result

