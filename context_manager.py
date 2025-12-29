import json
import os
import time
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from config import PATHS, CHROMA_CONFIG, EMBEDDING_MODEL, RAG_CONFIG

logger = logging.getLogger(__name__)

class ContextManager:
    def __init__(self):
        self.static_context: Dict[str, str] = {}
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        self._init_chroma()
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
            collections.append(CHROMA_CONFIG["collection_equipment"])

        execution_keywords = [
            "用什么工具", "怎么筛选", "buffer_filter_tool", "elevation_filter_tool",
            "vegetation_filter_tool", "slope_filter_tool", "链式", "工具链"
        ]
        if any(kw in query for kw in execution_keywords):
            collections.append(CHROMA_CONFIG["collection_executions"])

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
            collections.append(CHROMA_CONFIG["collection_knowledge"])

        if not collections:
            collections.append(CHROMA_CONFIG["collection_knowledge"])

        return list(set(collections))

    def _init_chroma(self):
        os.makedirs(PATHS["chroma_db_dir"], exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=PATHS["chroma_db_dir"],
            settings=Settings(anonymized_telemetry=False)
        )
        self._ensure_collections()

    def _ensure_collections(self):
        """确保所有collection存在，创建时显式指定cosine距离度量"""
        for collection_name in [CHROMA_CONFIG["collection_tasks"], 
                                CHROMA_CONFIG["collection_executions"],
                                CHROMA_CONFIG["collection_knowledge"],
                                CHROMA_CONFIG["collection_equipment"]]:
            try:
                self.chroma_client.get_collection(collection_name)
            except:
                self.chroma_client.create_collection(
                    collection_name,
                    metadata={"hnsw:space": "cosine"}
                )

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

        self._init_rag_data()

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

    def add_to_rag(self, text: str, metadata: Dict, collection: str = "default"):
        """添加文档到RAG数据库，使用UUID+时间戳生成唯一ID"""
        if collection == "default":
            collection = CHROMA_CONFIG["collection_executions"]

        coll = self.chroma_client.get_collection(collection)
        embedding = self._embed_passage(text)

        existing = coll.get()

        if collection == CHROMA_CONFIG["collection_executions"]:
            if existing['ids'] and len(existing['ids']) >= 30:
                metadatas = existing.get('metadatas', [])
                ids = existing['ids']

                items_with_time = []
                for i, meta in enumerate(metadatas):
                    created_at = meta.get('created_at', 0) if meta else 0
                    items_with_time.append((ids[i], created_at))

                items_with_time.sort(key=lambda x: x[1])
                oldest_id = items_with_time[0][0]
                coll.delete(ids=[oldest_id])

        timestamp_ms = int(time.time() * 1000)
        unique_suffix = uuid4().hex[:8]
        new_id = f"{collection}_{timestamp_ms}_{unique_suffix}"

        metadata_with_time = metadata.copy()
        metadata_with_time['created_at'] = timestamp_ms

        coll.add(
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata_with_time],
            ids=[new_id]
        )

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
                boost += RAG_CONFIG["metadata_boost_unit"]

        type_in_meta = metadata.get("type", "")
        if type_in_meta:
            if "部署" in query or "配置" in query:
                if type_in_meta == "deployment_rule":
                    boost += RAG_CONFIG["metadata_boost_type"]
            if "射程" in query:
                if type_in_meta == "equipment_info":
                    boost += RAG_CONFIG["metadata_boost_type"]

        tool_in_meta = metadata.get("tool", "")
        if tool_in_meta:
            if tool_in_meta in query or tool_in_meta in keywords:
                boost += RAG_CONFIG["metadata_boost_type"]

        return boost

    def _retrieve_from_collection(
        self, 
        collection: str, 
        query: str, 
        query_embedding: List[float],
        oversample: int
    ) -> List[Dict]:
        """从单个collection中检索候选文档"""
        coll = self.chroma_client.get_collection(collection)

        n_results = RAG_CONFIG["top_k"] * oversample
        results = coll.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        candidates = []
        if results["documents"] and len(results["documents"][0]) > 0:
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i] if results["distances"] else 1.0
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}

                candidates.append({
                    "text": doc,
                    "metadata": metadata,
                    "distance": distance,
                    "collection": collection
                })

        return candidates

    def load_dynamic_context(self, query: str, top_k: int = None, collection: str = None) -> List[Dict]:
        """混合检索：关键词粗召回 + 向量精排/融合，支持多库并查和距离阈值过滤"""
        if top_k is None:
            top_k = RAG_CONFIG["top_k"]

        if collection is None:
            target_collections = self._route_collection(query)
        else:
            if collection == "default":
                target_collections = [CHROMA_CONFIG["collection_executions"]]
            else:
                target_collections = [collection]

        logger.info(f"[RAG路由] query='{query}' → collections={target_collections}")

        query_embedding = self._embed_query(query)

        keywords = self._extract_keywords(query)
        logger.info(f"[RAG关键词] extracted keywords={keywords}")

        all_candidates = []
        for coll_name in target_collections:
            candidates = self._retrieve_from_collection(
                coll_name, query, query_embedding, RAG_CONFIG["oversample"]
            )
            all_candidates.extend(candidates)
            logger.info(f"[RAG召回] collection={coll_name}, candidates={len(candidates)}")

        if not all_candidates:
            logger.warning("[RAG] 未找到任何候选文档")
            return []

        max_distance = RAG_CONFIG["max_distance"]
        w_sem = RAG_CONFIG["w_sem"]
        w_kw = RAG_CONFIG["w_kw"]

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

        logger.info(f"[RAG过滤] 阈值过滤前={len(all_candidates)}, 过滤后={len(scored_candidates)}")

        min_k = RAG_CONFIG["min_k"]
        if len(scored_candidates) < min_k and len(all_candidates) > len(scored_candidates):
            relaxed_max_distance = max_distance + 0.5
            logger.warning(f"[RAG降级] 结果不足{min_k}条，放宽阈值至{relaxed_max_distance}")

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

        logger.info(f"[RAG最终结果] 返回{len(final_results)}条:")
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

    def _get_military_units_rules(self) -> List[Dict]:
        """获取军事单位部署规则列表

        注意：如果要修改部署规则，请修改此方法，然后运行 update_knowledge.py 更新数据库
        """
        return [
                {
                    "text": "轻步兵适合部署在中等高程区域，地形起伏不大，坡度以缓坡或平缓地形为主。部署地表类型可为树、灌木或草地，有利于隐蔽与灵活机动。配置位置与居民区及建筑保持100-300米缓冲距离，便于利用建筑边缘与自然掩体展开机动作战。",
                    "metadata": {"unit": "轻步兵", "type": "deployment_rule"}
                },
                {
                    "text": "重装步兵适合配置在较低至中等高程的防御阵地，坡度以平缓或中等坡度为宜。部署区域地表类型可为草地或裸地/稀疏植被，满足火力展开与阵地稳定需求。部署位置与居民区和建筑保持200-500米缓冲距离。",
                    "metadata": {"unit": "重装步兵", "type": "deployment_rule"}
                },
                {
                    "text": "机械化步兵更适合部署在中等高程的过渡地带，坡度为低至中等坡度，以保障装甲车辆通行。地表类型可选择草地或耕地。配置位置与居民区保持300-600米缓冲距离，兼顾机动效率与安全。",
                    "metadata": {"unit": "机械化步兵", "type": "deployment_rule"}
                },
                {
                    "text": "坦克部队适合部署在低至中等高程的开阔区域，整体坡度较为平缓。部署地表类型可为草地、耕地或裸地/稀疏植被，满足装甲单位机动与展开需求。配置位置与居民区和建筑保持500-1000米缓冲距离。",
                    "metadata": {"unit": "坦克", "type": "deployment_rule"}
                },
                {
                    "text": "反坦克步兵适合部署在中等至较高高程的伏击位置，坡度为中等坡度或局部陡坡。部署区域地表类型可为灌木、树或建筑边缘，利于隐蔽与形成俯射角度。与居民区保持150-400米缓冲距离。",
                    "metadata": {"unit": "反坦克步兵", "type": "deployment_rule"}
                },
                {
                    "text": "自行火炮通常部署在中等高程或背坡地形，坡度以缓坡为主，利于火炮稳定展开。部署地表类型可为草地或裸地/稀疏植被。配置位置与居民区保持600-1000米缓冲距离。",
                    "metadata": {"unit": "自行火炮", "type": "deployment_rule"}
                },
                {
                    "text": "牵引火炮适合配置在相对固定的中低高程阵地，地形坡度较小且稳定。部署区域地表类型可为草地或耕地。与居民区保持400-800米缓冲距离，确保持续火力覆盖。",
                    "metadata": {"unit": "牵引火炮", "type": "deployment_rule"}
                },
                {
                    "text": "防空部队适合部署在中等至较高高程位置，坡度为平缓或中等坡度。部署地表类型可为裸地/稀疏植被或草地，有利于雷达与火力视野展开。与居民区保持300-700米缓冲距离。",
                    "metadata": {"unit": "防空", "type": "deployment_rule"}
                },
                {
                    "text": "狙击手适合配置在较高高程制高点，局部坡度为中等或陡坡。部署区域地表类型可为树、灌木或建筑阴影区域，利于隐蔽观察与精确射击。与居民区保持50-200米缓冲距离。",
                    "metadata": {"unit": "狙击手", "type": "deployment_rule"}
                },
                {
                    "text": "特种部队适合部署在高程变化明显的复杂地形，坡度范围从缓坡到陡坡不等。部署地表类型可组合树、灌木、草地或湿地边缘，以提升渗透与隐蔽能力。与居民区保持200-500米缓冲距离。",
                    "metadata": {"unit": "特种部队", "type": "deployment_rule"}
                },
                {
                    "text": "装甲侦察单位适合部署在中低高程区域，整体坡度较为平缓，便于快速进出。部署地表类型可为草地或耕地。与居民区保持300-600米缓冲距离，以降低被发现概率。",
                    "metadata": {"unit": "装甲侦察单位", "type": "deployment_rule"}
                },
                {
                    "text": "工兵部队多部署在中低高程的关键节点区域，坡度相对平缓，便于工程作业展开。部署地表类型可为草地、耕地或建筑边缘区域。与居民区保持100-400米缓冲距离。",
                    "metadata": {"unit": "工兵部队", "type": "deployment_rule"}
                },
                {
                    "text": "后勤保障部队适合部署在低高程、安全区域，坡度平缓稳定，便于物资运输。部署地表类型可为建筑周边、草地或耕地。与居民区保持500-1000米缓冲距离。",
                    "metadata": {"unit": "后勤保障部队", "type": "deployment_rule"}
                },
                {
                    "text": "指挥单位适合部署在中等高程、地形相对隐蔽的位置，坡度为缓坡或平台地形。部署区域地表类型可为树、灌木或建筑掩护区。与居民区保持300-600米缓冲距离。",
                    "metadata": {"unit": "指挥单位", "type": "deployment_rule"}
                },
                {
                    "text": "无人机侦察控制单元适合部署在中高高程区域，坡度较小，确保设备稳定运行。部署地表类型可为裸地/稀疏植被或低矮草地。与居民区保持400-800米缓冲距离。",
                    "metadata": {"unit": "无人机", "type": "deployment_rule"}
                }
            ]

    def _get_equipment_info(self) -> List[Dict]:
        """获取装备信息列表（包含射程等信息）

        注意：如果要修改装备信息，请修改此方法，然后运行 update_equipment_base() 更新数据库
        装备信息应该包含：单位名称、装备类型、射程范围等
        """
        return [
                {
                    "text": "轻步兵主要装备突击步枪，有效射程300-400米，最大射程800米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "轻步兵", "type": "equipment_info", "range": "300-400", "max_range": "800"}
                },
                {
                    "text": "重装步兵主要装备重型机枪，有效射程400-500米，最大射程1000米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "重装步兵", "type": "equipment_info", "range": "400-500", "max_range": "1000"}
                },
                {
                    "text": "机械化步兵主要装备轻型坦克，有效射程500-600米，最大射程1200米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "机械化步兵", "type": "equipment_info", "range": "500-600", "max_range": "1200"}
                },
                {
                    "text": "坦克部队主要装备重型坦克，有效射程600-700米，最大射程1500米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "坦克部队", "type": "equipment_info", "range": "600-700", "max_range": "1500"}
                },
                {
                    "text": "反坦克步兵主要装备反坦克导弹，有效射程700-800米，最大射程1800米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "反坦克步兵", "type": "equipment_info", "range": "700-800", "max_range": "1800"}
                },
                {
                    "text": "自行火炮主要装备自行火炮，有效射程800-900米，最大射程2000米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "自行火炮", "type": "equipment_info", "range": "800-900", "max_range": "2000"}
                },
                {
                    "text": "牵引火炮主要装备牵引火炮，有效射程900-1000米，最大射程2200米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "牵引火炮", "type": "equipment_info", "range": "900-1000", "max_range": "2200"}
                },
                {
                    "text": "防空部队主要装备防空导弹，有效射程1000-1100米，最大射程2400米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "防空部队", "type": "equipment_info", "range": "1000-1100", "max_range": "2400"}
                },
                {
                    "text": "狙击手主要装备狙击步枪，有效射程1100-1200米，最大射程2600米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "狙击手", "type": "equipment_info", "range": "1100-1200", "max_range": "2600"}
                },
                {
                    "text": "特种部队主要装备特种武器，有效射程1200-1300米，最大射程2800米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "特种部队", "type": "equipment_info", "range": "1200-1300", "max_range": "2800"}
                },
                {
                    "text": "装甲侦察单位主要装备装甲侦察车，有效射程1300-1400米，最大射程3000米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "装甲侦察单位", "type": "equipment_info", "range": "1300-1400", "max_range": "3000"}
                },
                {
                    "text": "工兵部队主要装备工兵装备，有效射程1400-1500米，最大射程3200米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "工兵部队", "type": "equipment_info", "range": "1400-1500", "max_range": "3200"}
                },
                {
                    "text": "后勤保障部队主要装备后勤保障装备，有效射程1500-1600米，最大射程3400米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "后勤保障部队", "type": "equipment_info", "range": "1500-1600", "max_range": "3400"}
                },
                {
                    "text": "指挥单位主要装备指挥装备，有效射程1600-1700米，最大射程3600米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "指挥单位", "type": "equipment_info", "range": "1600-1700", "max_range": "3600"}
                },
                {
                    "text": "无人机侦察控制单元主要装备无人机侦察控制装备，有效射程1700-1800米，最大射程3800米。在规划缓冲区距离时，应考虑射程因素以确保火力覆盖范围。",
                    "metadata": {"unit": "无人机侦察控制单元", "type": "equipment_info", "range": "1700-1800", "max_range": "3800"}
                }
            ]

    def update_knowledge_base(self):
        """更新knowledge集合，清除旧数据并重新初始化军事单位部署规则"""
        try:
            knowledge_coll = self.chroma_client.get_collection(CHROMA_CONFIG["collection_knowledge"])
            existing_ids = knowledge_coll.get()["ids"]

            if existing_ids:
                knowledge_coll.delete(ids=existing_ids)

            military_units = self._get_military_units_rules()

            for i, unit in enumerate(military_units):
                embedding = self._embed_passage(unit["text"])
                knowledge_coll.add(
                    embeddings=[embedding],
                    documents=[unit["text"]],
                    metadatas=[unit["metadata"]],
                    ids=[f"knowledge_{i}"]
                )

            return len(military_units)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise Exception(f"更新知识库失败: {str(e)}")

    def update_equipment_base(self):
        """更新equipment集合，清除旧数据并重新初始化装备信息"""
        try:
            equipment_coll = self.chroma_client.get_collection(CHROMA_CONFIG["collection_equipment"])
            existing_ids = equipment_coll.get()["ids"]

            if existing_ids:
                equipment_coll.delete(ids=existing_ids)

            equipment_info = self._get_equipment_info()

            for i, equipment in enumerate(equipment_info):
                embedding = self._embed_passage(equipment["text"])
                equipment_coll.add(
                    embeddings=[embedding],
                    documents=[equipment["text"]],
                    metadatas=[equipment["metadata"]],
                    ids=[f"equipment_{i}"]
                )

            return len(equipment_info)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise Exception(f"更新装备信息库失败: {str(e)}")

    def _init_rag_data(self):
        knowledge_coll = self.chroma_client.get_collection(CHROMA_CONFIG["collection_knowledge"])
        executions_coll = self.chroma_client.get_collection(CHROMA_CONFIG["collection_executions"])
        equipment_coll = self.chroma_client.get_collection(CHROMA_CONFIG["collection_equipment"])

        existing_knowledge = knowledge_coll.get()
        existing_knowledge_ids = existing_knowledge["ids"]

        should_init = len(existing_knowledge_ids) == 0

        if not should_init:
            metadatas = existing_knowledge.get("metadatas", [])
            has_military_units = any(
                meta.get("type") == "deployment_rule" and "unit" in meta 
                for meta in metadatas if meta
            )
            if not has_military_units:
                should_init = True
                knowledge_coll.delete(ids=existing_knowledge_ids)

        if should_init:
            military_units = self._get_military_units_rules()

            for i, unit in enumerate(military_units):
                embedding = self._embed_passage(unit["text"])
                knowledge_coll.add(
                    embeddings=[embedding],
                    documents=[unit["text"]],
                    metadatas=[unit["metadata"]],
                    ids=[f"knowledge_{i}"]
                )
            print(f"已初始化 {len(military_units)} 条军事单位部署规则到knowledge集合")

        existing_equipment = equipment_coll.get()
        existing_equipment_ids = existing_equipment["ids"]

        should_init_equipment = len(existing_equipment_ids) == 0

        if not should_init_equipment:
            metadatas = existing_equipment.get("metadatas", [])
            has_equipment = any(
                meta.get("type") == "equipment_info" 
                for meta in metadatas if meta
            )
            if not has_equipment:
                should_init_equipment = True
                equipment_coll.delete(ids=existing_equipment_ids)

        if should_init_equipment:
            equipment_info = self._get_equipment_info()

            for i, equipment in enumerate(equipment_info):
                embedding = self._embed_passage(equipment["text"])
                equipment_coll.add(
                    embeddings=[embedding],
                    documents=[equipment["text"]],
                    metadatas=[equipment["metadata"]],
                    ids=[f"equipment_{i}"]
                )
            print(f"已初始化 {len(equipment_info)} 条装备信息到equipment集合")

        if len(executions_coll.get()["ids"]) == 0:
            sample_executions = [
                {
                    "text": "使用buffer_filter_tool，设置buffer_distance为500米，成功筛选出空地区域",
                    "metadata": {"tool": "buffer_filter_tool", "success": True}
                },
                {
                    "text": "使用elevation_filter_tool，设置min_elev为100，max_elev为500，成功筛选出符合高程要求的区域",
                    "metadata": {"tool": "elevation_filter_tool", "success": True}
                },
                {
                    "text": "先使用buffer_filter_tool筛选空地，然后使用elevation_filter_tool进一步筛选高程",
                    "metadata": {"tool": "chain", "success": True}
                },
                {
                    "text": "使用vegetation_filter_tool，设置vegetation_types为[30, 60]（草地和裸地），成功筛选出符合植被要求的区域",
                    "metadata": {"tool": "vegetation_filter_tool", "success": True}
                }
            ]

            for i, execution in enumerate(sample_executions):
                embedding = self._embed_passage(execution["text"])
                executions_coll.add(
                    embeddings=[embedding],
                    documents=[execution["text"]],
                    metadatas=[execution["metadata"]],
                    ids=[f"execution_{i}"]
                )
