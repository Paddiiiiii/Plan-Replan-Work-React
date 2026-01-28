from typing import Dict, List
from context_manager import ContextManager
import logging
import re

logger = logging.getLogger(__name__)

class PlanModule:
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager

    def generate_plan(self, user_task: str) -> Dict:
        """
        生成计划：直接使用原始任务调用KAG获取知识，然后传递给Work模块
        
        Args:
            user_task: 用户任务描述
            
        Returns:
            包含原始问题、KAG结果和合并答案的字典
        """
        logger.info(f"Plan阶段 - 开始处理用户任务: {user_task[:100]}...")
        
        # 直接使用原始任务调用KAG获取知识（不再拆分问题）
        logger.info(f"Plan阶段 - 直接使用原始任务进行KAG检索")
        
        # 对原始任务调用KAG获取知识
        kag_results = self._call_kag_for_questions([user_task])
        logger.info(f"Plan阶段 - KAG调用完成，获得 {len(kag_results)} 个结果")
        
        # 合并所有KAG答案
        combined_kag_answers = self._combine_kag_answers(kag_results)
        logger.info(f"Plan阶段 - 合并后的KAG答案长度: {len(combined_kag_answers)}")
        
        logger.info(f"Plan阶段 - 提取完成，source_texts已添加到kag_results中")
        
        # 从kag_results的tasks中提取实体和关系
        retrieved_entities = []
        retrieved_relations = []
        entity_id_set = set()  # 用于去重
        relation_key_set = set()  # 用于去重
        
        for kag_result in kag_results:
            tasks = kag_result.get("tasks", [])
            for task in tasks:
                # 从task的memory中提取
                task_memory = task.get("memory", {})
                if isinstance(task_memory, dict):
                    # 从retriever结果中提取实体和关系
                    if "retriever" in task_memory:
                        retriever_output = task_memory["retriever"]
                        self._extract_entities_relations_from_retriever_output(
                            retriever_output, retrieved_entities, retrieved_relations, entity_id_set, relation_key_set
                        )
                    
                    # 从graph_data中提取
                    if "graph_data" in task_memory:
                        graph_data = task_memory["graph_data"]
                        self._extract_entities_relations_from_graph_data(
                            graph_data, retrieved_entities, retrieved_relations, entity_id_set, relation_key_set
                        )
                
                # 从task的result中提取
                task_result = task.get("result")
                if task_result:
                    self._extract_entities_relations_from_retriever_output(
                        task_result, retrieved_entities, retrieved_relations, entity_id_set, relation_key_set
                    )
        
        logger.info(f"Plan阶段 - 提取到 {len(retrieved_entities)} 个实体, {len(retrieved_relations)} 个关系")
        
        # 构建返回结构（保持向后兼容，sub_questions包含原始任务）
        plan = {
            "original_query": user_task,
            "sub_questions": [user_task],  # 保持向后兼容
            "kag_results": kag_results,
            "combined_kag_answers": combined_kag_answers,
            "retrieved_entities": retrieved_entities,
            "retrieved_relations": retrieved_relations
        }
        
        # 在终端显示Plan结果
        print("\n" + "=" * 80)
        print("📋 Plan阶段结果（KAG知识召回）")
        print("=" * 80)
        print(f"原始问题: {user_task}")
        print(f"\nKAG知识召回结果:")
        for i, result in enumerate(kag_results, 1):
            answer_preview = result.get("answer", "")[:100]
            if len(result.get("answer", "")) > 100:
                answer_preview += "..."
            print(f"  问题: {result.get('question', '')[:80]}...")
            print(f"  答案: {answer_preview}")
        print("=" * 80 + "\n")
        
        return plan
    
    def _call_kag_for_questions(self, questions: List[str]) -> List[Dict]:
        """
        对每个子问题调用KAG获取知识
        
        Args:
            questions: 子问题列表
            
        Returns:
            KAG结果列表，每个元素包含 question, answer, tasks, input_query
        """
        kag_results = []
        
        for question in questions:
            try:
                logger.info(f"Plan阶段 - 调用KAG查询: {question[:50]}...")

                # 调用KAG推理（获取完整的tasks，包括实体和关系）
                kag_result = self.context_manager.query_with_kag_reasoning(question)

                # 清理KAG答案（移除reference标记等）
                clean_answer = self._clean_kag_answer(kag_result.get("answer", ""))

                # 获取tasks，如果为空则尝试从raw_result中提取
                tasks = kag_result.get("tasks", [])
                if not tasks and "raw_result" in kag_result:
                    raw_result = kag_result["raw_result"]
                    if isinstance(raw_result, dict) and "Tasks" in raw_result:
                        # 从raw_result中提取Tasks
                        # raw_result中的Tasks格式是: [{'task': {...}, {'task': {...}}, ...]
                        # 需要转换为标准格式: [{...}, {...}, ...]
                        raw_tasks = raw_result["Tasks"]
                        tasks = []
                        for item in raw_tasks:
                            if isinstance(item, dict) and "task" in item:
                                # 提取内部task
                                tasks.append(item["task"])
                            elif isinstance(item, dict):
                                # 如果已经是正确格式，直接添加
                                tasks.append(item)
                        logger.info(f"从raw_result中提取并转换了 {len(tasks)} 个tasks")

                # 从tasks的result.chunks中提取检索到的原文
                source_texts = []
                for task in tasks:
                    task_result = task.get("result")
                    if task_result and isinstance(task_result, dict):
                        chunks = task_result.get("chunks", [])
                        logger.debug(f"Task包含 {len(chunks)} 个检索到的chunks")

                        for chunk in chunks:
                            if isinstance(chunk, dict):
                                content = chunk.get("content", "")
                                title = chunk.get("title", "")
                                if content:
                                    source_texts.append({
                                        "title": title,
                                        "content": content,
                                        "chunk_id": chunk.get("chunk_id", ""),
                                        "score": chunk.get("score", 0)
                                    })

                kag_results.append({
                    "question": question,
                    "answer": clean_answer,
                    "tasks": tasks,
                    "input_query": kag_result.get("input_query", question),
                    "references": kag_result.get("references", []),  # 保留原始引用信息
                    "source_texts": source_texts  # 保留检索到的原文
                })
                
                logger.info(f"Plan阶段 - KAG查询完成，答案长度: {len(clean_answer)}")
                
            except Exception as e:
                logger.error(f"Plan阶段 - KAG查询失败 (问题: {question[:50]}): {e}", exc_info=True)
                # 如果KAG调用失败，仍添加一个空结果，确保流程继续
                kag_results.append({
                    "question": question,
                    "answer": "",
                    "tasks": [],
                    "input_query": question,
                    "references": []
                })
        
        return kag_results
    
    def _clean_kag_answer(self, answer: str) -> str:
        """
        清理KAG答案，移除reference标记等格式字符
        
        Args:
            answer: 原始KAG答案
            
        Returns:
            清理后的答案
        """
        if not answer:
            return ""
        
        # 移除reference标记
        clean = re.sub(r'<reference[^>]*></reference>', '', answer)
        
        # 移除可能的"Final Answer:"前缀
        clean = re.sub(r'Final\s+Answer\s*:?\s*', '', clean, flags=re.IGNORECASE)
        
        # 清理多余空白
        clean = re.sub(r'\n\s*\n', '\n\n', clean)  # 多个换行合并为两个
        clean = clean.strip()
        
        return clean
    
    def _combine_kag_answers(self, kag_results: List[Dict]) -> str:
        """
        合并所有KAG答案为一个文本
        
        Args:
            kag_results: KAG结果列表
            
        Returns:
            合并后的答案文本
        """
        combined_parts = []
        
        for i, result in enumerate(kag_results, 1):
            question = result.get("question", "")
            answer = result.get("answer", "")
            
            if answer:
                combined_parts.append(f"子问题{i}: {question}\n答案{i}: {answer}")
            else:
                combined_parts.append(f"子问题{i}: {question}\n答案{i}: （无相关信息）")
        
        return "\n\n".join(combined_parts)
    
    def _extract_entities_relations_from_retriever_output(self, retriever_output, retrieved_entities, retrieved_relations, entity_id_set, relation_key_set):
        """从retriever输出中提取实体和关系"""
        if isinstance(retriever_output, dict):
            # 检查是否有graph_data或kg_graph
            graph_data = retriever_output.get("graph_data") or retriever_output.get("kg_graph")
            if graph_data:
                self._extract_entities_relations_from_graph_data(
                    graph_data, retrieved_entities, retrieved_relations, entity_id_set, relation_key_set
                )
            
            # 检查是否有chunks，从chunks中提取实体和关系
            chunks = retriever_output.get("chunks", [])
            for chunk in chunks:
                if isinstance(chunk, dict):
                    # 尝试从chunk的metadata中提取实体和关系
                    chunk_metadata = chunk.get("metadata", {})
                    if chunk_metadata:
                        # 检查是否有实体和关系信息
                        entities = chunk_metadata.get("entities", [])
                        relations = chunk_metadata.get("relations", [])
                        if entities:
                            for entity in entities:
                                if isinstance(entity, dict):
                                    entity_id = entity.get("id") or entity.get("name", "")
                                    if entity_id and entity_id not in entity_id_set:
                                        entity_id_set.add(entity_id)
                                        retrieved_entities.append({
                                            "id": entity_id,
                                            "name": entity.get("name", entity_id),
                                            "type": entity.get("type") or entity.get("label", "Unknown"),
                                            "properties": entity.get("properties", {})
                                        })
                        if relations:
                            for relation in relations:
                                if isinstance(relation, dict):
                                    source = relation.get("source") or relation.get("from_id") or relation.get("from", "")
                                    target = relation.get("target") or relation.get("to_id") or relation.get("to", "")
                                    relation_type = relation.get("type") or relation.get("label", "Unknown")
                                    if source and target:
                                        relation_key = f"{source}->{target}->{relation_type}"
                                        if relation_key not in relation_key_set:
                                            relation_key_set.add(relation_key)
                                            retrieved_relations.append({
                                                "source": source,
                                                "target": target,
                                                "type": relation_type,
                                                "properties": relation.get("properties", {})
                                            })
    
    def _extract_entities_relations_from_graph_data(self, graph_data, retrieved_entities, retrieved_relations, entity_id_set, relation_key_set):
        """从graph_data中提取实体和关系"""
        if isinstance(graph_data, dict):
            # 提取节点（实体）
            nodes = graph_data.get("nodes", graph_data.get("resultNodes", []))
            if not nodes and "result_nodes" in graph_data:
                nodes = graph_data.get("result_nodes", [])
            
            for node in nodes:
                if isinstance(node, dict):
                    entity_id = node.get("id") or node.get("name", "")
                    if entity_id and entity_id not in entity_id_set:
                        entity_id_set.add(entity_id)
                        retrieved_entities.append({
                            "id": entity_id,
                            "name": node.get("name", entity_id),
                            "type": node.get("type") or node.get("label", "Unknown"),
                            "properties": node.get("properties", {})
                        })
            
            # 提取边（关系）
            edges = graph_data.get("edges", graph_data.get("resultEdges", []))
            if not edges and "result_edges" in graph_data:
                edges = graph_data.get("result_edges", [])
            
            for edge in edges:
                if isinstance(edge, dict):
                    source = edge.get("from_id") or edge.get("from") or edge.get("source", "")
                    target = edge.get("to_id") or edge.get("to") or edge.get("target", "")
                    relation_type = edge.get("label") or edge.get("type", "Unknown")
                    if source and target:
                        relation_key = f"{source}->{target}->{relation_type}"
                        if relation_key not in relation_key_set:
                            relation_key_set.add(relation_key)
                            retrieved_relations.append({
                                "source": source,
                                "target": target,
                                "type": relation_type,
                                "properties": edge.get("properties", {})
                            })
        elif hasattr(graph_data, "result_nodes") and hasattr(graph_data, "result_edges"):
            # 如果是KgGraph对象，尝试转换为字典
            try:
                if hasattr(graph_data, "to_dict"):
                    graph_dict = graph_data.to_dict()
                    self._extract_entities_relations_from_graph_data(
                        graph_dict, retrieved_entities, retrieved_relations, entity_id_set, relation_key_set
                    )
                else:
                    # 直接从对象属性提取
                    nodes = getattr(graph_data, "result_nodes", [])
                    edges = getattr(graph_data, "result_edges", [])
                    for node in nodes:
                        if hasattr(node, "id"):
                            entity_id = getattr(node, "id", "")
                            if entity_id and entity_id not in entity_id_set:
                                entity_id_set.add(entity_id)
                                retrieved_entities.append({
                                    "id": entity_id,
                                    "name": getattr(node, "name", entity_id),
                                    "type": getattr(node, "label", "Unknown"),
                                    "properties": getattr(node, "properties", {}) if hasattr(node, "properties") else {}
                                })
                    for edge in edges:
                        if hasattr(edge, "from_id") or hasattr(edge, "_from"):
                            source = getattr(edge, "from_id", "") or getattr(edge, "_from", "")
                            target = getattr(edge, "to_id", "") or getattr(edge, "to", "")
                            relation_type = getattr(edge, "label", "Unknown")
                            if source and target:
                                relation_key = f"{source}->{target}->{relation_type}"
                                if relation_key not in relation_key_set:
                                    relation_key_set.add(relation_key)
                                    retrieved_relations.append({
                                        "source": source,
                                        "target": target,
                                        "type": relation_type,
                                        "properties": getattr(edge, "properties", {}) if hasattr(edge, "properties") else {}
                                    })
            except Exception as e:
                logger.debug(f"从graph_data对象提取实体和关系失败: {e}")
