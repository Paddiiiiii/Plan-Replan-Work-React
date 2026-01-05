import json
import logging
import time
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
import requests

logger = logging.getLogger(__name__)

from context.kag.openspg_adapter import OpenSPGAdapter

class KAGAdapter:
    """OpenSPG KAG适配器，提供知识图谱构建和查询接口"""
    
    def __init__(self, embedding_model_name: str, llm_config: Dict, kag_config: Dict, kg_storage_path: str, use_openspg: bool = True):
        self.embedding_model_name = embedding_model_name
        self.llm_config = llm_config
        self.kag_config = kag_config
        self.kg_storage_path = Path(kg_storage_path)
        self.kg_storage_path.mkdir(parents=True, exist_ok=True)
        
        self.embedding_model = SentenceTransformer(embedding_model_name)
        
        self.entities = {}
        self.relations = []
        self.entity_embeddings = {}
        
        try:
            self.openspg_adapter = OpenSPGAdapter(
                kg_storage_path=str(kg_storage_path),
                embedding_model_name=embedding_model_name,
                llm_config=llm_config
            )
            logger.info("已启用OpenSPG原生抽取")
        except Exception as e:
            logger.error(f"OpenSPG适配器初始化失败: {e}")
            raise RuntimeError(
                "OpenSPG SDK未正确安装或初始化失败。"
                "请按照 OPENSPG_INSTALL.md 中的说明安装OpenSPG KAG SDK。"
                f"错误详情: {e}"
            )
        
        self._load_kg()
    
    def _load_kg(self):
        """从文件加载知识图谱"""
        kg_file = self.kg_storage_path / "kg.json"
        if kg_file.exists():
            try:
                with open(kg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.entities = data.get("entities", {})
                    self.relations = data.get("relations", [])
                    self.entity_embeddings = data.get("embeddings", {})
                logger.info(f"已加载知识图谱: {len(self.entities)} 个实体, {len(self.relations)} 个关系")
            except Exception as e:
                logger.warning(f"加载知识图谱失败: {e}，将创建新的知识图谱")
                self.entities = {}
                self.relations = []
                self.entity_embeddings = {}
        else:
            logger.info("知识图谱文件不存在，将创建新的知识图谱")
    
    def _save_kg(self):
        """保存知识图谱到文件"""
        kg_file = self.kg_storage_path / "kg.json"
        try:
            data = {
                "entities": self.entities,
                "relations": self.relations,
                "embeddings": self.entity_embeddings
            }
            with open(kg_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存知识图谱: {len(self.entities)} 个实体, {len(self.relations)} 个关系")
        except Exception as e:
            logger.error(f"保存知识图谱失败: {e}")
            raise
    
    def _embed_text(self, text: str, prefix: str = "passage") -> List[float]:
        """对文本进行embedding"""
        prefixed_text = f"{prefix}: {text}"
        return self.embedding_model.encode(prefixed_text).tolist()
    
    def add_entity(self, entity_type: str, entity_id: str, properties: Dict, text: str = None):
        """添加实体到知识图谱"""
        if text is None:
            text = properties.get("text", "")
        
        entity = {
            "id": entity_id,
            "type": entity_type,
            "properties": properties,
            "text": text,
            "created_at": int(time.time() * 1000)
        }
        
        self.entities[entity_id] = entity
        
        embedding = self._embed_text(text, "passage")
        self.entity_embeddings[entity_id] = embedding
        
        self._save_kg()
        logger.debug(f"已添加实体: {entity_type}/{entity_id}")
    
    def add_relation(self, relation_type: str, source_id: str, target_id: str, properties: Dict = None):
        """添加关系到知识图谱"""
        if properties is None:
            properties = {}
        
        relation = {
            "type": relation_type,
            "source": source_id,
            "target": target_id,
            "properties": properties,
            "created_at": int(time.time() * 1000)
        }
        
        self.relations.append(relation)
        self._save_kg()
        logger.debug(f"已添加关系: {relation_type} ({source_id} -> {target_id})")
    
    def query(self, query_text: str, entity_types: List[str] = None, top_k: int = 5, 
              max_distance: float = 0.35, use_llm_reasoning: bool = False) -> List[Dict]:
        """查询知识图谱
        
        Args:
            query_text: 查询文本
            entity_types: 限制查询的实体类型列表
            top_k: 返回top_k个结果
            max_distance: 最大距离阈值
            use_llm_reasoning: 是否使用LLM进行逻辑推理
        
        Returns:
            查询结果列表，每个结果包含text、metadata、distance等字段
        """
        query_embedding = self._embed_text(query_text, "query")
        
        candidates = []
        
        for entity_id, entity in self.entities.items():
            if entity_types and entity["type"] not in entity_types:
                continue
            
            entity_embedding = self.entity_embeddings.get(entity_id)
            if entity_embedding is None:
                continue
            
            distance = self._cosine_distance(query_embedding, entity_embedding)
            
            if distance <= max_distance:
                candidates.append({
                    "entity_id": entity_id,
                    "entity_type": entity["type"],
                    "text": entity.get("text", ""),
                    "metadata": entity.get("properties", {}),
                    "distance": distance,
                    "semantic_score": 1.0 - distance
                })
        
        candidates.sort(key=lambda x: x["distance"])
        
        if use_llm_reasoning and candidates:
            candidates = self._llm_rerank(query_text, candidates)
        
        results = candidates[:top_k]
        
        for result in results:
            result["keyword_score"] = 0.0
            result["metadata_boost"] = 0.0
            result["final_score"] = result.get("semantic_score", 1.0 - result["distance"])
            result["collection"] = result.get("entity_type", "unknown")
        
        return results
    
    def _cosine_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦距离"""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 1.0
        cosine_sim = dot_product / (norm1 * norm2)
        return 1.0 - cosine_sim
    
    def _llm_rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """使用LLM对候选结果进行重排序"""
        try:
            prompt = f"""根据以下查询，对候选结果进行排序，返回最相关的top {len(candidates)}个结果。

查询: {query}

候选结果:
{json.dumps([{"text": c["text"], "metadata": c["metadata"]} for c in candidates], ensure_ascii=False, indent=2)}

请返回JSON格式的排序结果，格式: [{{"index": 0, "relevance_score": 0.9}}]
"""
            
            response = requests.post(
                self.llm_config["api_endpoint"],
                json={
                    "model": self.llm_config["model"],
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1000
                },
                timeout=self.llm_config.get("timeout", 30)
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                try:
                    rerank_scores = json.loads(content)
                    if isinstance(rerank_scores, list):
                        score_map = {item["index"]: item.get("relevance_score", 0.5) for item in rerank_scores}
                        for i, candidate in enumerate(candidates):
                            if i in score_map:
                                candidate["llm_score"] = score_map[i]
                                candidate["final_score"] = (candidate["semantic_score"] * 0.7 + score_map[i] * 0.3)
                        candidates.sort(key=lambda x: x.get("final_score", x["semantic_score"]), reverse=True)
                except:
                    pass
        except Exception as e:
            logger.warning(f"LLM重排序失败: {e}，使用原始排序")
        
        return candidates
    
    def delete_entity(self, entity_id: str):
        """删除实体"""
        if entity_id in self.entities:
            del self.entities[entity_id]
        if entity_id in self.entity_embeddings:
            del self.entity_embeddings[entity_id]
        
        self.relations = [r for r in self.relations if r["source"] != entity_id and r["target"] != entity_id]
        
        self._save_kg()
        logger.debug(f"已删除实体: {entity_id}")
    
    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """获取实体"""
        return self.entities.get(entity_id)
    
    def get_entities_by_type(self, entity_type: str) -> List[Dict]:
        """根据类型获取所有实体（支持旧类型到新类型的映射）"""
        # 类型映射：旧类型 -> 新类型
        type_mapping = {
            "MilitaryUnit": "OperationalUnit",
            "Equipment": "CapabilityProfile"
        }
        
        # 获取对应的OpenSPG类型
        openspg_type = type_mapping.get(entity_type, entity_type)
        
        entities = []
        for entity_id, entity in self.entities.items():
            # 同时支持旧类型和新类型查询
            entity_type_in_kg = entity.get("type")
            if entity_type_in_kg == entity_type or entity_type_in_kg == openspg_type:
                entities.append({
                    "id": entity_id,
                    "type": entity["type"],
                    "properties": entity.get("properties", {}),
                    "text": entity.get("text", "")
                })
        return entities
    
    def extract_entities_from_text(self, text: str, entity_type: str, collection_name: str) -> int:
        """从文本中提取实体和关系并添加到知识图谱
        
        使用OpenSPG原生抽取方法
        
        Args:
            text: 输入文本
            entity_type: 实体类型（如 "Equipment", "MilitaryUnit"）
            collection_name: 集合名称（如 "equipment", "knowledge"）
        
        Returns:
            提取并添加的实体数量
        """
        if not self.openspg_adapter:
            raise RuntimeError("OpenSPG适配器未初始化，无法进行知识抽取")
        return self._extract_with_openspg(text, entity_type, collection_name)
    
    def _chunk_text(self, text: str, chunk_size: int = 6, overlap: int = 2) -> List[Tuple[str, int, int]]:
        """将文本切分为chunks，带overlap
        
        Args:
            text: 输入文本
            chunk_size: 每个chunk包含的句子数（4-8句）
            overlap: chunk之间的重叠句子数（1-2句）
        
        Returns:
            List of (chunk_text, start_idx, end_idx) tuples
        """
        # 按句号、分号、换行符切分句子
        sentences = re.split(r'([。；\n])', text)
        # 重新组合，保留分隔符
        combined_sentences = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                combined_sentences.append(sentences[i] + sentences[i + 1])
            else:
                combined_sentences.append(sentences[i])
        
        if len(sentences) % 2 == 1:
            combined_sentences.append(sentences[-1])
        
        # 过滤空句子
        combined_sentences = [s.strip() for s in combined_sentences if s.strip()]
        
        if not combined_sentences:
            return [(text, 0, len(text))]
        
        chunks = []
        i = 0
        while i < len(combined_sentences):
            # 取chunk_size个句子
            end_idx = min(i + chunk_size, len(combined_sentences))
            chunk_sentences = combined_sentences[i:end_idx]
            chunk_text = ''.join(chunk_sentences)
            
            # 计算在原文中的位置
            start_pos = text.find(chunk_sentences[0]) if chunk_sentences else 0
            end_pos = start_pos + len(chunk_text)
            
            chunks.append((chunk_text, start_pos, end_pos))
            
            # 下一个chunk的起始位置：减去overlap
            i = end_idx - overlap
            if i >= len(combined_sentences):
                break
        
        logger.info(f"文本切分为 {len(chunks)} 个chunks（每chunk约{chunk_size}句，overlap {overlap}句）")
        return chunks
    
    def _extract_with_openspg(self, text: str, entity_type: str, collection_name: str) -> int:
        """使用OpenSPG原生抽取方法（支持文本切分）"""
        # P2-2: 创建日志目录
        log_dir = self.kg_storage_path / "logs" / f"extract_{time.strftime('%Y%m%d')}"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"extract_{int(time.time() * 1000)}.json"
        
        # 记录输入文本的前100个字符用于日志
        text_preview = text[:100] + "..." if len(text) > 100 else text
        logger.info(f"开始抽取实体，文本预览: {text_preview}")
        
        # P0-1: 文本切分
        chunks = self._chunk_text(text, chunk_size=6, overlap=2)
        
        # P2-2: 记录抽取日志
        extraction_log = {
            "timestamp": int(time.time() * 1000),
            "text_preview": text_preview,
            "text_length": len(text),
            "chunks": [],
            "final_entities": [],
            "final_relations": []
        }
        
        extraction_config = {
            "method": "llm",
            "schema": self._get_schema_for_type(entity_type)
        }
        
        # 对每个chunk进行抽取，然后合并结果
        all_entities = []
        all_relations = []
        
        for chunk_idx, (chunk_text, start_pos, end_pos) in enumerate(chunks):
            logger.info(f"处理chunk {chunk_idx + 1}/{len(chunks)} (位置: {start_pos}-{end_pos})")
            result = self.openspg_adapter.extract_from_text(
                chunk_text, 
                extraction_config,
                chunk_info={"chunk_idx": chunk_idx, "start_pos": start_pos, "end_pos": end_pos}
            )
            chunk_entities = result.get("entities", [])
            chunk_relations = result.get("relations", [])
            
            # 为每个实体添加chunk信息
            for entity in chunk_entities:
                entity["_chunk_idx"] = chunk_idx
                entity["_chunk_start"] = start_pos
                entity["_chunk_end"] = end_pos
                entity["_chunk_text"] = chunk_text  # 保存chunk文本用于证据验证
            
            all_entities.extend(chunk_entities)
            all_relations.extend(chunk_relations)
            
            # P2-2: 记录chunk抽取日志
            extraction_log["chunks"].append({
                "chunk_idx": chunk_idx,
                "start_pos": start_pos,
                "end_pos": end_pos,
                "chunk_text": chunk_text,
                "entities_count": len(chunk_entities),
                "relations_count": len(chunk_relations),
                "entities": chunk_entities,
                "relations": chunk_relations
            })
        
        logger.info(f"OpenSPG返回了 {len(all_entities)} 个实体和 {len(all_relations)} 个关系（来自{len(chunks)}个chunks）")
        
        entities_data = all_entities
        relations_data = all_relations
        
        # P2-1: 实体和关系去重（跨chunk合并）
        entity_map = {}  # 用于存储已添加的实体 (normalized_name, category) -> entity_id
        relation_set = set()  # 用于关系去重 (source, relation_type, target)
        added_count = 0
        
        # 定义无效实体关键词（占位符、示例等）
        invalid_keywords = [
            "实体名称", "实体类型", "示例实体", "实体", "名称", "类型",
            "马云", "阿里巴巴", "苹果", "乔布斯", "沃兹尼亚克", "库比蒂诺",
            "iphone", "ipad", "mac电脑", "浙江省杭州市"
        ]
        
        # P1-1: 定义允许的实体类型和关系类型白名单
        allowed_entity_types = ["OperationalUnit", "CapabilityProfile", "DeploymentConstraint", "PlaceFeature"]
        allowed_relation_types = ["hasCapability", "hasDeploymentConstraint", "suitableOn", "constraintRefersTo"]
        
        def normalize_name(name: str) -> str:
            """标准化实体名称（用于去重）"""
            # 去空格、统一大小写、去全角半角差异
            name = name.strip()
            # 可以添加更多标准化规则
            return name
        
        for entity_data in entities_data:
            entity_name = entity_data.get("name", "")
            if not entity_name:
                continue
            
            # P0-3: 证据约束验证
            chunk_text = entity_data.get("_chunk_text", "")
            evidence_text = entity_data.get("properties", {}).get("evidence_text", "")
            
            # 验证evidence_text必须在chunk_text中
            if evidence_text:
                if evidence_text not in chunk_text:
                    logger.warning(f"过滤实体（证据不在chunk中）: {entity_name}, evidence: {evidence_text[:50]}")
                    continue
                # 验证entity_name必须在evidence_text中
                if entity_name not in evidence_text:
                    logger.warning(f"过滤实体（名称不在证据中）: {entity_name}, evidence: {evidence_text[:50]}")
                    continue
            else:
                # 如果没有evidence_text，检查entity_name是否在chunk_text中
                if entity_name not in chunk_text:
                    logger.warning(f"过滤实体（无证据且名称不在chunk中）: {entity_name}")
                    continue
            
            # 过滤无效实体：占位符、示例等
            entity_name_lower = entity_name.lower()
            is_invalid = False
            for keyword in invalid_keywords:
                if keyword.lower() in entity_name_lower or entity_name_lower == keyword.lower():
                    logger.warning(f"过滤无效实体: {entity_name} (包含关键词: {keyword})")
                    is_invalid = True
                    break
            
            if is_invalid:
                continue
            
            # P1-1: 验证实体类型是否在白名单中
            entity_category = entity_data.get("category", "")
            if entity_category not in allowed_entity_types:
                logger.warning(f"过滤实体（类型不在白名单）: {entity_name}, category: {entity_category}")
                continue
            
            # P2-1: 实体去重
            normalized_name = normalize_name(entity_name)
            dedup_key = (normalized_name, entity_category)
            if dedup_key in entity_map:
                logger.debug(f"跳过重复实体: {entity_name} (已存在: {entity_map[dedup_key]})")
                continue
            
            properties = entity_data.get("properties", {})
            
            # 清理properties，移除过长的文本内容（可能是整个原始文本）
            cleaned_properties = {}
            for key, value in properties.items():
                # 跳过内部字段
                if key.startswith("_"):
                    continue
                # 如果value是字符串且长度超过200，可能是整个原始文本，只保留前200字符
                if isinstance(value, str) and len(value) > 200:
                    logger.debug(f"截断过长的属性值: {key} (长度: {len(value)} -> 200)")
                    cleaned_properties[key] = value[:200] + "..."
                else:
                    cleaned_properties[key] = value
            
            # P1-2: 数值字段normalize（范围拆min/max）
            # 处理范围字符串，如 "300-400" -> effectiveRangeMin=300, effectiveRangeMax=400
            range_pattern = r'(\d+)\s*[-~至]\s*(\d+)'
            for key, value in list(cleaned_properties.items()):
                if isinstance(value, str):
                    # 检查是否是范围格式
                    match = re.search(range_pattern, value)
                    if match:
                        min_val = int(match.group(1))
                        max_val = int(match.group(2))
                        # 根据key名称决定如何拆分
                        if "range" in key.lower() or "射程" in value or "距离" in value:
                            if "effective" in key.lower() or "有效" in value:
                                cleaned_properties["effectiveRangeMin"] = min_val
                                cleaned_properties["effectiveRangeMax"] = max_val
                            else:
                                cleaned_properties["maxRange"] = max_val
                        elif "buffer" in key.lower() or "缓冲" in value:
                            cleaned_properties["bufferMin"] = min_val
                            cleaned_properties["bufferMax"] = max_val
                        # 保留原始值作为note
                        if "note" not in cleaned_properties:
                            cleaned_properties["note"] = value
                    # 处理单值，如 "800" -> maxRange=800
                    elif re.match(r'^\d+$', value.strip()):
                        num_val = int(value.strip())
                        if "range" in key.lower() or "射程" in key or "距离" in key:
                            if "max" in key.lower() or "最大" in key:
                                cleaned_properties["maxRange"] = num_val
                            else:
                                cleaned_properties["effectiveRangeMax"] = num_val
            
            # 设置text属性为实体名称（而不是整个原始文本）
            if "text" not in cleaned_properties:
                cleaned_properties["text"] = entity_name
            else:
                # 如果text属性存在但过长，替换为实体名称
                text_value = cleaned_properties.get("text", "")
                if isinstance(text_value, str) and len(text_value) > 200:
                    cleaned_properties["text"] = entity_name
            
            properties = cleaned_properties
            
            timestamp_ms = int(time.time() * 1000)
            unique_suffix = f"{added_count:04d}"
            entity_id = f"{collection_name}_{timestamp_ms}_{unique_suffix}"
            
            openspg_entity_type = self._map_to_openspg_type(entity_type)
            # 使用self.add_entity保存到本地知识图谱，而不是openspg_adapter.add_entity
            self.add_entity(
                entity_type=openspg_entity_type,
                entity_id=entity_id,
                properties=properties,
                text=properties.get("text", entity_name)
            )
            
            entity_map[entity_name] = entity_id
            added_count += 1
        
        for relation_data in relations_data:
            source_name = relation_data.get("source", "")
            target_name = relation_data.get("target", "")
            relation_type = relation_data.get("relation_type", "RelatedTo")
            
            # P1-1: 验证关系类型是否在白名单中
            if relation_type not in allowed_relation_types:
                logger.warning(f"过滤关系（类型不在白名单）: {source_name} -[{relation_type}]-> {target_name}")
                continue
            
            # P2-1: 关系去重
            dedup_key = (source_name, relation_type, target_name)
            if dedup_key in relation_set:
                logger.debug(f"跳过重复关系: {source_name} -[{relation_type}]-> {target_name}")
                continue
            
            if source_name in entity_map and target_name in entity_map:
                # 使用self.add_relation保存到本地知识图谱，而不是openspg_adapter.add_relation
                self.add_relation(
                    relation_type=relation_type,
                    source_id=entity_map[source_name],
                    target_id=entity_map[target_name],
                    properties=relation_data.get("properties", {})
                )
                relation_set.add(dedup_key)
            else:
                logger.debug(f"跳过关系（实体不存在）: {source_name} -[{relation_type}]-> {target_name}")
        
        logger.info(f"使用OpenSPG提取了 {added_count} 个有效实体和 {len(relation_set)} 个关系（过滤前原始实体数: {len(entities_data)}, 原始关系数: {len(relations_data)}）")
        return added_count
    
    def _map_to_openspg_type(self, old_type: str) -> str:
        """将旧的实体类型映射到OpenSPG类型"""
        mapping = {
            "Equipment": "CapabilityProfile",
            "MilitaryUnit": "OperationalUnit"
        }
        return mapping.get(old_type, "OperationalUnit")
    
    def _get_schema_for_type(self, entity_type: str) -> str:
        """获取特定实体类型的Schema定义"""
        from context.kag.openspg_schema import SCHEMA_DEFINITION
        return SCHEMA_DEFINITION

