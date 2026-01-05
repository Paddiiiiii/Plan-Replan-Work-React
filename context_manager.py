import json
import os
import time
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4
from sentence_transformers import SentenceTransformer
from config import PATHS, EMBEDDING_MODEL, KAG_CONFIG, LLM_CONFIG
from context.kag.kag_adapter import KAGAdapter
from context.kag.schema import COLLECTION_TO_ENTITY_TYPE

logger = logging.getLogger(__name__)

class ContextManager:
    def __init__(self):
        self.static_context: Dict[str, str] = {}
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        self._init_kag()
        self._load_static_context()

    def _embed_query(self, query: str) -> List[float]:
        """对查询文本进行embedding，添加query前缀（BGE模型优化）"""
        prefixed_query = f"query: {query}"
        return self.embedding_model.encode(prefixed_query).tolist()

    def _embed_passage(self, text: str) -> List[float]:
        """对文档文本进行embedding，添加passage前缀（BGE模型优化）"""
        prefixed_text = f"passage: {text}"
        return self.embedding_model.encode(prefixed_text).tolist()

    def _route_collection(self, query: str) -> List[str]:
        """根据查询内容路由到相应的collection(s)，支持多库并查"""
        query_lower = query.lower()
        collections = []
        
        equipment_keywords = ["射程", "最大射程", "range", "max_range", "有效射程"]
        if any(kw in query for kw in equipment_keywords):
            collections.append("equipment")
        
        knowledge_keywords = [
            "部署", "配置", "坡度", "高程", "缓冲距离", "地表", "隐蔽", "机动"
        ]
        unit_names = [
            "轻步兵", "重装步兵", "机械化步兵", "坦克部队", "反坦克步兵",
            "自行火炮", "牵引火炮", "防空部队", "狙击手", "特种部队",
            "装甲侦察单位", "工兵部队", "后勤保障部队", "指挥单位", "无人机侦察控制单元"
        ]
        has_unit = any(unit in query for unit in unit_names)
        
        if any(kw in query for kw in knowledge_keywords) or has_unit:
            collections.append("knowledge")
        
        if not collections:
            collections.append("knowledge")
        
        return list(set(collections))

    def _init_kag(self):
        """初始化KAG知识图谱适配器"""
        use_openspg = KAG_CONFIG.get("use_openspg", True)
        self.kag = KAGAdapter(
            use_openspg=use_openspg,
            embedding_model_name=KAG_CONFIG["embedding_model"],
            llm_config=LLM_CONFIG,
            kag_config=KAG_CONFIG,
            kg_storage_path=KAG_CONFIG["kg_storage_path"]
        )
        logger.info("KAG知识图谱适配器初始化完成")

    def _load_static_context(self):
        static_file = PATHS["static_context_dir"] / "prompts.json"
        if static_file.exists():
            with open(static_file, "r", encoding="utf-8") as f:
                self.static_context = json.load(f)
        else:
            raise FileNotFoundError(
                f"提示词文件不存在: {static_file}\n"
                "请创建 context/static/prompts.json 文件，包含 plan_prompt, replan_prompt, work_prompt, system_prompt 字段"
            )
        
        # 不再自动初始化知识图谱数据
        # 只有在通过API、更新脚本或前端明确调用update_knowledge_base()或update_equipment_base()时才会进行抽取
        logger.info("知识图谱已加载，等待用户主动更新")

    def _save_static_context(self):
        os.makedirs(PATHS["static_context_dir"], exist_ok=True)
        static_file = PATHS["static_context_dir"] / "prompts.json"
        with open(static_file, "w", encoding="utf-8") as f:
            json.dump(self.static_context, f, ensure_ascii=False, indent=2)

    def save_static_context(self, context_type: str, content: str):
        self.static_context[context_type] = content
        self._save_static_context()

    def load_static_context(self, context_type: str) -> str:
        return self.static_context.get(context_type, "")

    def add_to_rag(self, text: str, metadata: Dict, collection: str = "knowledge"):
        """添加文档到KAG知识图谱，使用UUID+时间戳生成唯一ID"""
        entity_type = COLLECTION_TO_ENTITY_TYPE.get(collection, "MilitaryUnit")

        timestamp_ms = int(time.time() * 1000)
        unique_suffix = uuid4().hex[:8]
        entity_id = f"{collection}_{timestamp_ms}_{unique_suffix}"

        properties = metadata.copy()
        properties['created_at'] = timestamp_ms
        properties['text'] = text

        self.kag.add_entity(
            entity_type=entity_type,
            entity_id=entity_id,
            properties=properties,
            text=text
        )
        
        logger.debug(f"已添加实体到KAG: {entity_type}/{entity_id}")

    def _extract_keywords(self, query: str) -> List[str]:
        """从查询中提取关键词：中文词块、数字、下划线、工具名等"""
        keywords = []

        chinese_words = re.findall(r'[\u4e00-\u9fff]+', query)
        keywords.extend(chinese_words)

        numbers = re.findall(r'\d+', query)
        keywords.extend(numbers)

        tool_names = [
            "buffer_filter_tool", "elevation_filter_tool", 
            "vegetation_filter_tool", "slope_filter_tool"
        ]
        for tool in tool_names:
            if tool in query.lower():
                keywords.append(tool)

        unit_names = [
            "轻步兵", "重装步兵", "机械化步兵", "坦克部队", "反坦克步兵",
            "自行火炮", "牵引火炮", "防空部队", "狙击手", "特种部队",
            "装甲侦察单位", "工兵部队", "后勤保障部队", "指挥单位", "无人机侦察控制单元"
        ]
        for unit in unit_names:
            if unit in query:
                keywords.append(unit)

        return list(set(keywords))

    def _calculate_keyword_score(self, doc_text: str, keywords: List[str]) -> float:
        """计算文档的关键词匹配分数"""
        if not keywords:
            return 0.0

        doc_lower = doc_text.lower()
        score = 0.0

        for keyword in keywords:
            if keyword.isdigit() or "tool" in keyword.lower():
                weight = 2.0
            else:
                weight = 1.0

            count = doc_lower.count(keyword.lower())
            score += count * weight

        return score / len(keywords) if keywords else 0.0

    def _calculate_metadata_boost(self, metadata: Dict, query: str, keywords: List[str]) -> float:
        """计算元数据匹配加分：unit/type/tool强约束"""
        boost = 0.0
        if not metadata:
            return boost

        unit_in_meta = metadata.get("unit", "")
        if unit_in_meta:
            if unit_in_meta in query or unit_in_meta in keywords:
                boost += KAG_CONFIG["metadata_boost_unit"]

        type_in_meta = metadata.get("type", "")
        if type_in_meta:
            if "部署" in query or "配置" in query:
                if type_in_meta == "deployment_rule":
                    boost += KAG_CONFIG["metadata_boost_type"]
            if "射程" in query:
                if type_in_meta == "equipment_info":
                    boost += KAG_CONFIG["metadata_boost_type"]

        tool_in_meta = metadata.get("tool", "")
        if tool_in_meta:
            if tool_in_meta in query or tool_in_meta in keywords:
                boost += KAG_CONFIG["metadata_boost_type"]

        return boost

    def _retrieve_from_collection(
        self, 
        collection: str, 
        query: str, 
        query_embedding: List[float],
        oversample: int
    ) -> List[Dict]:
        """从KAG知识图谱中检索候选实体"""
        entity_type = COLLECTION_TO_ENTITY_TYPE.get(collection, "MilitaryUnit")
        n_results = KAG_CONFIG["top_k"] * oversample
        
        results = self.kag.query(
            query_text=query,
            entity_types=[entity_type] if entity_type else None,
            top_k=n_results,
            max_distance=KAG_CONFIG["max_distance"] * 2,
            use_llm_reasoning=KAG_CONFIG.get("use_llm_reasoning", False)
        )

        candidates = []
        for result in results:
            candidates.append({
                "text": result["text"],
                "metadata": result["metadata"],
                "distance": result["distance"],
                "collection": collection
            })

        return candidates

    def load_dynamic_context(self, query: str, top_k: int = None, collection: str = None) -> List[Dict]:
        """混合检索：关键词粗召回 + 向量精排/融合，支持多库并查和距离阈值过滤"""
        if top_k is None:
            top_k = KAG_CONFIG["top_k"]

        if collection is None:
            target_collections = self._route_collection(query)
        else:
            target_collections = [collection]

        logger.info(f"[KAG路由] query='{query}' → collections={target_collections}")

        keywords = self._extract_keywords(query)
        logger.info(f"[KAG关键词] extracted keywords={keywords}")

        all_candidates = []
        for coll_name in target_collections:
            query_embedding = self._embed_query(query)
            candidates = self._retrieve_from_collection(
                coll_name, query, query_embedding, KAG_CONFIG["oversample"]
            )
            all_candidates.extend(candidates)
            logger.info(f"[KAG召回] collection={coll_name}, candidates={len(candidates)}")

        if not all_candidates:
            logger.warning("[KAG] 未找到任何候选文档")
            return []

        max_distance = KAG_CONFIG["max_distance"]
        w_sem = KAG_CONFIG["w_sem"]
        w_kw = KAG_CONFIG["w_kw"]

        scored_candidates = []
        for candidate in all_candidates:
            distance = candidate["distance"]

            if distance > max_distance:
                continue

            semantic_score = 1.0 - distance

            keyword_score = self._calculate_keyword_score(candidate["text"], keywords)

            metadata_boost = self._calculate_metadata_boost(
                candidate["metadata"], query, keywords
            )

            final_score = w_sem * semantic_score + w_kw * keyword_score + metadata_boost

            scored_candidates.append({
                **candidate,
                "semantic_score": semantic_score,
                "keyword_score": keyword_score,
                "metadata_boost": metadata_boost,
                "final_score": final_score
            })

        scored_candidates.sort(key=lambda x: x["final_score"], reverse=True)

        logger.info(f"[KAG过滤] 阈值过滤前={len(all_candidates)}, 过滤后={len(scored_candidates)}")

        min_k = KAG_CONFIG["min_k"]
        if len(scored_candidates) < min_k and len(all_candidates) > len(scored_candidates):
            relaxed_distance_increment = KAG_CONFIG.get("relaxed_distance_increment", 0.5)
            relaxed_max_distance = max_distance + relaxed_distance_increment
            logger.warning(f"[KAG降级] 结果不足{min_k}条，放宽阈值至{relaxed_max_distance}")

            for candidate in all_candidates:
                if candidate["distance"] <= relaxed_max_distance:
                    if not any(c["text"] == candidate["text"] for c in scored_candidates):
                        distance = candidate["distance"]
                        semantic_score = 1.0 - distance
                        keyword_score = self._calculate_keyword_score(candidate["text"], keywords)
                        metadata_boost = self._calculate_metadata_boost(
                            candidate["metadata"], query, keywords
                        )
                        final_score = w_sem * semantic_score + w_kw * keyword_score + metadata_boost

                        scored_candidates.append({
                            **candidate,
                            "semantic_score": semantic_score,
                            "keyword_score": keyword_score,
                            "metadata_boost": metadata_boost,
                            "final_score": final_score,
                            "low_confidence": True
                        })

            scored_candidates.sort(key=lambda x: x["final_score"], reverse=True)

        final_results = scored_candidates[:top_k]

        logger.info(f"[KAG最终结果] 返回{len(final_results)}条:")
        for i, result in enumerate(final_results):
            logger.info(
                f"  [{i+1}] collection={result['collection']}, "
                f"distance={result['distance']:.3f}, "
                f"semantic={result['semantic_score']:.3f}, "
                f"keyword={result['keyword_score']:.3f}, "
                f"metadata_boost={result['metadata_boost']:.3f}, "
                f"final={result['final_score']:.3f}, "
                f"low_confidence={result.get('low_confidence', False)}"
            )

        contexts = []
        for result in final_results:
            contexts.append({
                "text": result["text"],
                "metadata": result["metadata"],
                "distance": result["distance"],
                "semantic_score": result["semantic_score"],
                "keyword_score": result["keyword_score"],
                "metadata_boost": result["metadata_boost"],
                "final_score": result["final_score"],
                "low_confidence": result.get("low_confidence", False),
                "collection": result["collection"]
            })

        return contexts

    def save_context(self, context_id: str, data: Dict):
        context_file = PATHS["context_dir"] / f"{context_id}.json"
        with open(context_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_context(self, context_id: str) -> Optional[Dict]:
        context_file = PATHS["context_dir"] / f"{context_id}.json"
        if context_file.exists():
            with open(context_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def compress_context(self, context: Dict, max_tokens: int = 2000) -> Dict:
        if len(str(context)) < max_tokens:
            return context

        compressed = {
            "summary": str(context)[:max_tokens],
            "full_length": len(str(context))
        }
        return compressed

    def update_knowledge_base(self):
        """更新knowledge集合，清除旧数据并重新初始化军事单位部署规则"""
        try:
            from update_knowledge import get_military_units_rules
            
            existing_entities = self.kag.get_entities_by_type("MilitaryUnit")
            for entity in existing_entities:
                self.kag.delete_entity(entity["id"])

            knowledge_text = get_military_units_rules()
            count = self.kag.extract_entities_from_text(
                text=knowledge_text,
                entity_type="MilitaryUnit",
                collection_name="knowledge"
            )

            return count
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise Exception(f"更新知识库失败: {str(e)}")

    def update_equipment_base(self):
        """更新equipment集合，清除旧数据并重新初始化装备信息"""
        try:
            from update_equipment import get_equipment_info
            
            existing_entities = self.kag.get_entities_by_type("Equipment")
            for entity in existing_entities:
                self.kag.delete_entity(entity["id"])

            equipment_text = get_equipment_info()
            count = self.kag.extract_entities_from_text(
                text=equipment_text,
                entity_type="Equipment",
                collection_name="equipment"
            )

            return count
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise Exception(f"更新装备信息库失败: {str(e)}")

