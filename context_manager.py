import json
import os
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from sentence_transformers import SentenceTransformer
import torch
from config import PATHS, EMBEDDING_MODEL, KAG_CONFIG
# KAG solver 已移到 KAG 项目内部

logger = logging.getLogger(__name__)

class ContextManager:
    def __init__(self):
        self.static_context: Dict[str, str] = {}
        # 保存最近一次KAG推理的完整答案文本，用于在plan阶段展示
        self.last_kag_answer: str = ""
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"使用设备: {device} 进行embedding计算")
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL, device=device)
        self._init_kag_solver()
        self._load_static_context()

    def _embed_query(self, query: str) -> List[float]:
        """对查询文本进行embedding，添加query前缀（BGE模型优化）"""
        prefixed_query = f"query: {query}"
        return self.embedding_model.encode(prefixed_query).tolist()

    def _embed_passage(self, text: str) -> List[float]:
        """对文档文本进行embedding，添加passage前缀（BGE模型优化）"""
        prefixed_text = f"passage: {text}"
        return self.embedding_model.encode(prefixed_text).tolist()

    
    def _init_kag_solver(self):
        """初始化KAG推理问答器（新版，基于KAG开发者模式）"""
        try:
            # 导入KAG项目内部的solver wrapper
            import sys
            from pathlib import Path
            
            # 添加KAG路径（确保kag模块可以被导入）
            # __file__ 是 context_manager.py，parent 是 AIgen 目录
            base_dir = Path(__file__).parent
            kag_path = base_dir / "KAG"
            kag_path_str = str(kag_path.resolve())  # 使用绝对路径
            
            if kag_path_str not in sys.path:
                sys.path.insert(0, kag_path_str)
                logger.debug(f"已添加KAG路径到sys.path: {kag_path_str}")
            
            # 验证KAG目录和kag模块是否存在
            kag_module_path = kag_path / "kag"
            if not kag_module_path.exists():
                raise FileNotFoundError(f"KAG模块目录不存在: {kag_module_path}")
            
            # 先测试kag模块是否可以导入
            try:
                import KAG.kag as kag
                logger.debug(f"KAG模块导入成功，路径: {getattr(kag, '__file__', 'unknown')}")
            except ImportError as e:
                logger.error(f"无法导入kag模块: {e}")
                logger.error(f"KAG路径: {kag_path_str}")
                logger.error(f"KAG目录存在: {kag_path.exists()}")
                logger.error(f"kag模块目录存在: {kag_module_path.exists()}")
                logger.error(f"当前sys.path前5项: {sys.path[:5]}")
                raise
            
            # 导入KAG solver wrapper
            from KAG.kag.examples.MilitaryDeployment.solver.kag_solver_wrapper import KAGSolverWrapper
            
            # 创建solver实例
            self.kag_solver = KAGSolverWrapper()
            logger.info("KAG推理问答器初始化完成")
        except Exception as e:
            logger.warning(f"KAG推理器初始化失败: {e}", exc_info=True)
            self.kag_solver = None

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
        
        logger.info("静态上下文已加载")

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

    def get_kg_data(self) -> Dict:
        """获取知识图谱数据（实体和关系）"""
        if self.kag_solver:
            return self.kag_solver.get_kg_data()
        return {
            "entities": [],
            "relations": [],
            "entity_count": 0,
            "relation_count": 0,
            "error": "KAG推理器未初始化"
        }

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

    def _retrieve_from_kag(
        self, 
        query: str, 
        query_embedding: List[float],
        oversample: int
    ) -> List[Dict]:
        """从KAG知识图谱中检索候选实体（使用KAG推理器）"""
        # 使用新的KAG推理器进行检索
        if self.kag_solver:
            try:
                result = self.kag_solver.query(query)
                # 记录本次KAG推理的完整答案，供plan阶段展示使用（避免重复调用KAG）
                try:
                    self.last_kag_answer = result.get("answer") or result.get("raw_result") or ""
                except Exception:
                    self.last_kag_answer = ""
                # 将KAG推理结果转换为检索格式
                candidates = []
                
                # 如果有references，使用references
                references = result.get("references", [])
                if references and len(references) > 0:
                    for ref in references:
                        candidates.append({
                            "text": ref.get("text", ""),
                            "metadata": ref.get("metadata", {}),
                            "distance": ref.get("distance", 0.0)
                        })
                
                # 如果没有references但有answer，将answer作为文本上下文返回
                if not candidates and result.get("answer"):
                    answer = result.get("answer", "")
                    # 清理reference标记，保留纯文本
                    import re
                    clean_answer = re.sub(r'<reference[^>]*></reference>', '', answer)
                    clean_answer = clean_answer.strip()
                    
                    if clean_answer:
                        candidates.append({
                            "text": clean_answer,
                            "metadata": {
                                "source": "kag_reasoning",
                                "type": "answer",
                                "query": query
                            },
                            "distance": 0.0  # KAG推理结果，距离设为0表示高相关性
                        })
                        logger.info(f"[KAG] 使用推理答案作为上下文，长度: {len(clean_answer)}")
                
                # 如果有raw_result且是字符串，也尝试使用
                if not candidates and result.get("raw_result"):
                    raw_result = result.get("raw_result")
                    if isinstance(raw_result, str) and raw_result.strip():
                        import re
                        clean_text = re.sub(r'<reference[^>]*></reference>', '', raw_result)
                        clean_text = clean_text.strip()
                        if clean_text:
                            candidates.append({
                                "text": clean_text,
                                "metadata": {
                                    "source": "kag_reasoning",
                                    "type": "raw_result",
                                    "query": query
                                },
                                "distance": 0.0
                            })
                            logger.info(f"[KAG] 使用原始结果作为上下文，长度: {len(clean_text)}")
                
                return candidates
            except Exception as e:
                logger.warning(f"KAG推理器检索失败: {e}", exc_info=True)
        
        # 如果KAG推理器不可用，返回空结果
        logger.warning("KAG推理器未初始化，返回空结果")
        return []

    def load_dynamic_context(self, query: str, top_k: int = None) -> List[Dict]:
        """
        从KAG知识图谱检索上下文
        
        Args:
            query: 查询文本
            top_k: 返回结果数量，默认使用配置值
            
        Returns:
            检索到的上下文列表
        """
        if top_k is None:
            top_k = KAG_CONFIG["top_k"]

        logger.info(f"[KAG检索] query='{query}'")

        keywords = self._extract_keywords(query)
        logger.info(f"[KAG关键词] extracted keywords={keywords}")

        query_embedding = self._embed_query(query)
        all_candidates = self._retrieve_from_kag(
            query, query_embedding, KAG_CONFIG["oversample"]
        )
        logger.info(f"[KAG召回] candidates={len(all_candidates)}")

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
                f"  [{i+1}] distance={result['distance']:.3f}, "
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
                "low_confidence": result.get("low_confidence", False)
            })

        return contexts
    
    def query_with_kag_reasoning(self, question: str) -> Dict:
        """
        使用KAG推理能力回答问题
        
        Args:
            question: 用户问题
            
        Returns:
            包含答案和引用的字典
        """
        if not self.kag_solver:
            logger.warning("KAG推理器未初始化")
            return {
                "answer": "",
                "references": [],
                "error": "KAG推理器未初始化"
            }
        
        try:
            # 先获取上下文
            context = self.load_dynamic_context(question, top_k=3)
            result = self.kag_solver.query_with_context(question, context)
            return result
        except Exception as e:
            logger.error(f"KAG推理查询失败: {e}", exc_info=True)
            return {
                "answer": "",
                "references": [],
                "error": str(e)
            }



