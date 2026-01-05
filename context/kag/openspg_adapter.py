"""OpenSPG KAG原生适配器，使用OpenSPG SDK进行知识抽取和图谱构建"""

import json
import logging
import time
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

OPENSPG_AVAILABLE = False
try:
    import knext
    from kag.builder.component.extractor.schema_free_extractor import SchemaFreeExtractor
    from kag.interface import LLMClient
    from kag.builder.model.chunk import Chunk
    from kag.builder.model.sub_graph import SubGraph
    OPENSPG_AVAILABLE = True
except ImportError as e:
    OPENSPG_AVAILABLE = False
    logger.debug(f"OpenSPG SDK未安装: {e}")

from context.kag.openspg_schema import ENTITY_TYPES, RELATION_TYPES, SCHEMA_DEFINITION


class CustomSchemaFreeExtractor(SchemaFreeExtractor):
    """自定义的SchemaFreeExtractor，避免SchemaClient初始化问题"""
    
    def __init__(self, llm: LLMClient, **kwargs):
        # 先设置kag_project_config，避免SchemaClient初始化失败
        from types import SimpleNamespace
        mock_config = SimpleNamespace()
        mock_config.host_addr = None
        mock_config.project_id = None
        mock_config.biz_scene = kwargs.get("biz_scene", "default")
        mock_config.language = kwargs.get("language", "zh")
        
        # 在调用super().__init__之前设置kag_project_config
        # 但我们需要先调用super().__init__来设置kag_project_config
        # 所以我们需要重写整个初始化过程
        
        # 直接调用父类的父类（BuilderComponent）的__init__
        from kag.interface.builder.base import BuilderComponent
        BuilderComponent.__init__(self, **kwargs)
        
        # 手动设置kag_project_config
        self.kag_project_config = mock_config
        
        # 设置LLM
        self.llm = llm
        
        # 创建mock schema，避免SchemaClient调用
        from types import SimpleNamespace
        mock_schema = SimpleNamespace()
        mock_schema.get = lambda x: SimpleNamespace(properties={})
        self.schema = mock_schema
        
        # 初始化prompts（使用简单的Prompt类，避免SchemaClient问题）
        from kag.interface import PromptABC
        import re
        
        class SimplePrompt(PromptABC):
            def __init__(self, template: str, language: str = "zh"):
                # 手动设置kag_project_config，避免SchemaClient调用
                from types import SimpleNamespace
                mock_config = SimpleNamespace()
                mock_config.project_id = None
                mock_config.language = language
                
                # 直接设置属性，避免调用super().__init__
                self.kag_project_config = mock_config
                self.language = language
                self.template_zh = template
                self.template_en = template
                self.template = template
                self.template_variables_value = {}
                self.example_input = None
                self.example_output = None
            
            @property
            def template_variables(self):
                """从模板中提取变量名"""
                # 使用正则表达式提取 {variable} 格式的变量
                pattern = r'\{(\w+)\}'
                variables = re.findall(pattern, self.template)
                return list(set(variables))
            
            def parse_response(self, response, **kwargs):
                """解析LLM响应"""
                import json
                
                # 如果response已经是list或dict，直接返回
                if isinstance(response, list):
                    return response
                elif isinstance(response, dict):
                    return [response]
                
                # 如果是字符串，尝试解析JSON
                if not isinstance(response, str):
                    logger.warning(f"无法解析响应类型: {type(response)}")
                    return []
                
                try:
                    # 尝试解析JSON
                    if '```json' in response:
                        start = response.find('```json') + 7
                        end = response.find('```', start)
                        response = response[start:end].strip()
                    elif '```' in response:
                        start = response.find('```') + 3
                        end = response.find('```', start)
                        response = response[start:end].strip()
                    
                    result = json.loads(response)
                    # 确保返回列表
                    if isinstance(result, list):
                        return result
                    elif isinstance(result, dict):
                        return [result]
                    else:
                        return []
                except Exception as e:
                    response_str = str(response)[:200] if response else ""
                    logger.warning(f"解析LLM响应失败: {e}, 响应: {response_str}")
                    # 如果解析失败，返回空列表
                    return []
        
        # 使用改进的prompt模板，明确要求只从输入文本中提取，不要返回示例
        # P0-3: 增加证据约束要求
        ner_template = """请从以下文本中识别命名实体，只提取文本中实际出现的实体，不要返回示例或占位符。

输入文本：
{input}

要求：
1. 只提取文本中实际出现的实体
2. 不要返回"实体名称"、"实体类型"、"示例实体"等占位符
3. 不要返回与输入文本无关的实体（如马云、乔布斯、苹果公司等）
4. 实体名称必须来自输入文本
5. 每个实体必须提供evidence_text字段，包含该实体在原文中的实际片段（至少3个字符）

返回JSON格式：
[
  {{
    "name": "实际实体名称",
    "category": "实体类型",
    "properties": {{}},
    "evidence_text": "实体在原文中的实际片段"
  }}
]"""
        
        std_template = """请对以下实体进行标准化，只处理文本中实际出现的实体。

输入文本：
{input}

实体列表：
{named_entities}

要求：
1. 只处理输入文本中实际出现的实体
2. 不要返回示例或占位符
3. 如果实体不在输入文本中，请忽略

返回JSON格式：
[
  {{"name": "实体名称", "category": "实体类型", "official_name": "标准名称"}}
]"""
        
        triple_template = """请从以下文本中提取三元组关系，只提取文本中实际存在的关系。

输入文本：
{input}

实体列表：
{entity_list}

要求：
1. 只提取输入文本中实际存在的关系
2. 主体和客体都必须在输入文本中出现
3. 不要返回示例或虚构的关系
4. 关系类型必须是：hasCapability、hasDeploymentConstraint、suitableOn、constraintRefersTo之一

返回JSON格式：
[
  ["主体名称", "关系类型", "客体名称"]
]"""
        
        self.ner_prompt = kwargs.get("ner_prompt") or SimplePrompt(ner_template, language="zh")
        self.std_prompt = kwargs.get("std_prompt") or SimplePrompt(std_template, language="zh")
        self.triple_prompt = kwargs.get("triple_prompt") or SimplePrompt(triple_template, language="zh")
        self.external_graph = kwargs.get("external_graph")
        
        # 初始化table_extractor（如果需要，但暂时设为None）
        self.table_extractor = None


class OpenSPGLLMClient(LLMClient):
    """适配本地LLM配置的OpenSPG LLMClient"""
    
    def __init__(self, llm_config: Dict, **kwargs):
        super().__init__(**kwargs)
        self.llm_config = llm_config
        self.model = llm_config.get("model", "qwen3:32b")  # 添加model属性
        import requests
        self.requests = requests
    
    def __call__(self, prompt, **kwargs):
        """调用LLM API"""
        if isinstance(prompt, dict):
            messages = prompt.get("messages", [{"role": "user", "content": str(prompt)}])
        else:
            messages = [{"role": "user", "content": str(prompt)}]
        
        response = self.requests.post(
            self.llm_config["api_endpoint"],
            json={
                "model": self.llm_config["model"],
                "messages": messages,
                "temperature": self.llm_config.get("temperature", 0.7),
                "max_tokens": self.llm_config.get("max_tokens", 4096)
            },
            timeout=self.llm_config.get("timeout", 180)
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            raise RuntimeError(f"LLM API调用失败: {response.status_code}")
    
    def to_config(self):
        """返回LLM配置（用于Extractor初始化）"""
        return {
            "type": "openai",
            "api_key": "",
            "base_url": self.llm_config["api_endpoint"],
            "model": self.llm_config["model"]
        }


class OpenSPGAdapter:
    """OpenSPG KAG原生适配器"""
    
    def __init__(self, kg_storage_path: str, embedding_model_name: str = None, llm_config: Dict = None):
        if not OPENSPG_AVAILABLE:
            raise RuntimeError(
                "OpenSPG SDK未安装！\n"
                "请按照以下步骤安装：\n"
                "1. git clone https://github.com/OpenSPG/KAG.git\n"
                "2. cd KAG\n"
                "3. pip install -e .\n"
                "详细说明请查看 OPENSPG_INSTALL.md"
            )
        
        self.kg_storage_path = Path(kg_storage_path)
        self.kg_storage_path.mkdir(parents=True, exist_ok=True)
        self.embedding_model_name = embedding_model_name
        self.llm_config = llm_config or {}
        
        try:
            # 初始化LLMClient
            if llm_config:
                self.llm_client = OpenSPGLLMClient(llm_config=llm_config)
            else:
                raise RuntimeError("需要提供llm_config来初始化OpenSPG适配器")
            
            # 初始化Extractor（使用自定义的SchemaFreeExtractor，避免SchemaClient问题）
            self.extractor = CustomSchemaFreeExtractor(
                llm=self.llm_client,
                biz_scene="default",
                language="zh"
            )
            
            logger.info("OpenSPG SDK已初始化")
        except Exception as e:
            logger.error(f"OpenSPG SDK初始化失败: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(
                f"OpenSPG SDK初始化失败: {e}\n"
                "请确保OpenSPG SDK已正确安装并配置。"
            )
    
    def extract_from_text(self, text: str, extraction_config: Dict = None, chunk_info: Dict = None) -> Dict:
        """使用OpenSPG原生抽取方法从文本中提取实体和关系
        
        Args:
            text: 输入文本
            extraction_config: 抽取配置（暂时未使用，保留接口兼容性）
            chunk_info: chunk信息（用于日志和证据验证）
        
        Returns:
            包含entities和relations的字典
        
        Raises:
            RuntimeError: 如果OpenSPG SDK不可用或抽取失败
        """
        try:
            # 创建Chunk对象
            chunk = Chunk(
                id=f"chunk_{int(time.time() * 1000)}",
                name="知识抽取",
                content=text
            )
            
            # 使用Extractor进行抽取
            subgraphs = self.extractor._invoke(chunk)
            
            if not subgraphs:
                return {"entities": [], "relations": []}
            
            subgraph = subgraphs[0]
            
            # P0-2: 构建id到name的映射
            id2name = {}
            for node in subgraph.nodes:
                id2name[node.id] = node.name
            
            # 转换SubGraph为entities和relations格式
            entities = []
            relations = []
            
            for node in subgraph.nodes:
                # 清理properties，移除OpenSPG内部字段（id, name, content等）和过长的文本
                properties = node.properties or {}
                cleaned_properties = {}
                for key, value in properties.items():
                    # 跳过OpenSPG内部字段
                    if key in ["id", "name", "content"]:
                        continue
                    # 如果value是字符串且长度超过500，可能是整个原始文本，跳过
                    if isinstance(value, str) and len(value) > 500:
                        logger.debug(f"跳过过长的属性值: {key} (长度: {len(value)})")
                        continue
                    cleaned_properties[key] = value
                
                entity = {
                    "name": node.name,
                    "category": node.label,
                    "properties": cleaned_properties,
                    "_node_id": node.id  # 保存node.id用于关系映射
                }
                entities.append(entity)
            
            # P0-2: 修复关系映射，使用name而不是id
            for edge in subgraph.edges:
                source_name = id2name.get(edge.from_id, edge.from_id)
                target_name = id2name.get(edge.to_id, edge.to_id)
                
                relation = {
                    "source": source_name,  # 使用name而不是id
                    "target": target_name,  # 使用name而不是id
                    "relation_type": edge.label,
                    "properties": edge.properties or {}
                }
                relations.append(relation)
            
            return {
                "entities": entities,
                "relations": relations
            }
        except Exception as e:
            logger.error(f"OpenSPG抽取失败: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"OpenSPG抽取失败: {e}")
    
    def add_entity(self, entity_type: str, entity_id: str, properties: Dict, text: str = None):
        """添加实体到知识图谱（暂时只记录，不实际存储到OpenSPG）"""
        logger.debug(f"已添加实体: {entity_type}/{entity_id}")
        # 注意：OpenSPG KAG的实体添加需要通过Builder Chain或Graph API
        # 这里暂时只记录日志，实际存储由KAGAdapter管理
    
    def add_relation(self, relation_type: str, source_id: str, target_id: str, properties: Dict = None):
        """添加关系到知识图谱（暂时只记录，不实际存储到OpenSPG）"""
        logger.debug(f"已添加关系: {relation_type} ({source_id} -> {target_id})")
        # 注意：OpenSPG KAG的关系添加需要通过Builder Chain或Graph API
        # 这里暂时只记录日志，实际存储由KAGAdapter管理
    
    def query(self, query_text: str, entity_types: List[str] = None, top_k: int = 5) -> List[Dict]:
        """查询知识图谱（暂时未实现）"""
        logger.warning("OpenSPG查询功能暂未实现")
        return []

