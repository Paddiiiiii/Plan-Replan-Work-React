import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from config import PATHS, CHROMA_CONFIG, EMBEDDING_MODEL, RAG_CONFIG


class ContextManager:
    def __init__(self):
        self.static_context: Dict[str, str] = {}
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        self._init_chroma()
        self._load_static_context()
    
    def _init_chroma(self):
        os.makedirs(PATHS["chroma_db_dir"], exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=PATHS["chroma_db_dir"],
            settings=Settings(anonymized_telemetry=False)
        )
        self._ensure_collections()
    
    def _ensure_collections(self):
        for collection_name in [CHROMA_CONFIG["collection_tasks"], 
                                CHROMA_CONFIG["collection_executions"],
                                CHROMA_CONFIG["collection_knowledge"],
                                CHROMA_CONFIG["collection_equipment"]]:
            try:
                self.chroma_client.get_collection(collection_name)
            except:
                self.chroma_client.create_collection(collection_name)
    
    def _load_static_context(self):
        static_file = PATHS["static_context_dir"] / "prompts.json"
        if static_file.exists():
            with open(static_file, "r", encoding="utf-8") as f:
                self.static_context = json.load(f)
        else:
            self._init_default_prompts()
            self._save_static_context()
        
        self._init_rag_data()
    
    def _init_default_prompts(self):
        self.static_context = {
            "plan_prompt": """你是一个任务规划助手，负责将用户的任务分解为可执行的步骤。

你的职责：
1. 理解用户任务的目标和要求
2. 将任务分解为清晰的步骤
3. 不涉及具体工具，只描述需要做什么

可用工具类型：
- buffer_filter: 缓冲区筛选（根据建筑和道路距离筛选）
- elevation_filter: 高程筛选（根据高程范围筛选）
- slope_filter: 坡度筛选（根据坡度范围筛选）
- vegetation_filter: 植被筛选（根据植被类型筛选）

输出格式（JSON）：
{
    "task": "用户原始任务",
    "goal": "任务目标描述",
    "steps": [
        {"step_id": 1, "description": "步骤描述", "type": "buffer/elevation/slope/vegetation"},
        ...
    ],
    "estimated_steps": 步骤数量
}

注意：只描述任务目标，不指定具体工具和参数。""",
            
            "replan_prompt": """你是一个重新规划助手，当执行失败时需要调整计划。

你的职责：
1. 分析执行失败的原因
2. 根据可用工具重新规划
3. 生成包含具体工具和参数的详细计划

可用工具：
{tools_info}

输出格式（JSON）：
{
    "task": "用户原始任务",
    "goal": "调整后的任务目标",
    "steps": [
        {"step_id": 1, "tool": "buffer_filter_tool", "params": {"buffer_distance": 500}},
        {"step_id": 2, "tool": "elevation_filter_tool", "params": {"input_geojson_path": "...", "min_elev": 100, "max_elev": 500}},
        {"step_id": 3, "tool": "vegetation_filter_tool", "params": {"input_geojson_path": "...", "vegetation_types": [30, 60]}},
        ...
    ],
    "required_tools": ["buffer_filter_tool", "elevation_filter_tool", "vegetation_filter_tool"],
    "reason": "重新规划的原因"
}""",
            
            "work_prompt": """你是一个执行助手，负责根据计划步骤执行具体操作。

你的职责：
1. 分析步骤描述，理解需要做什么
2. 选择合适的工具和参数
3. 返回执行动作

可用工具：
- buffer_filter_tool: 缓冲区筛选工具
  参数: buffer_distance (必需), utm_crs (可选)
  
- elevation_filter_tool: 高程筛选工具
  参数: input_geojson_path (必需), min_elev (可选), max_elev (可选)
  
- slope_filter_tool: 坡度筛选工具
  参数: input_geojson_path (必需), min_slope (可选), max_slope (可选)
  
- vegetation_filter_tool: 植被筛选工具
  参数: input_geojson_path (必需), vegetation_types (可选), exclude_types (可选)

输出格式（JSON）：
{
    "tool": "工具名称",
    "params": {
        "参数名": "参数值"
    }
}

注意：
- buffer_filter_tool的输出可以作为elevation_filter_tool、slope_filter_tool和vegetation_filter_tool的input_geojson_path
- 如果步骤描述包含"距离"、"缓冲区"等关键词，使用buffer_filter_tool
- 如果步骤描述包含"高程"、"海拔"等关键词，使用elevation_filter_tool
- 如果步骤描述包含"坡度"、"倾斜"等关键词，使用slope_filter_tool
- 如果步骤描述包含"植被"、"草地"、"林地"、"树木"、"耕地"、"裸地"、"水体"等关键词，使用vegetation_filter_tool
- 如果步骤描述包含"植被"、"草地"、"林地"、"树木"、"耕地"、"裸地"、"水体"等关键词，使用vegetation_filter_tool""",
            
            "system_prompt": """你是一个专业的空地分析智能体，专门处理地理空间数据的筛选和分析任务。

你的能力包括：
1. 理解用户的地理空间分析需求
2. 规划合理的分析流程
3. 执行地理空间筛选操作
4. 根据执行结果调整策略

工作原则：
- 仔细分析用户需求
- 合理规划执行步骤
- 准确选择工具和参数
- 及时处理错误和异常"""
        }
    
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
        if collection == "default":
            collection = CHROMA_CONFIG["collection_executions"]
        
        coll = self.chroma_client.get_collection(collection)
        embedding = self.embedding_model.encode(text).tolist()
        
        existing = coll.get()
        new_id = f"{collection}_{len(existing['ids']) if existing['ids'] else 0}"
        
        coll.add(
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata],
            ids=[new_id]
        )
    
    def load_dynamic_context(self, query: str, top_k: int = None, collection: str = "default") -> List[Dict]:
        if top_k is None:
            top_k = RAG_CONFIG["top_k"]
        
        if collection == "default":
            collection = CHROMA_CONFIG["collection_executions"]
        
        coll = self.chroma_client.get_collection(collection)
        query_embedding = self.embedding_model.encode(query).tolist()
        
        results = coll.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        contexts = []
        if results["documents"] and len(results["documents"][0]) > 0:
            for i, doc in enumerate(results["documents"][0]):
                contexts.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None
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
                    "text": "轻步兵适合部署在中等高程区域，地形起伏不大，坡度以缓坡或平缓地形为主。区域内宜具备中等覆盖度的天然植被，如灌木、零散乔木或混合草木带，以提供隐蔽与机动掩护，同时避免过密植被影响快速展开。配置位置应与居民区保持100-300米的缓冲距离，既能避免直接暴露于民用区域，又便于利用建筑边缘与自然掩体展开机动作战。",
                    "metadata": {"unit": "轻步兵", "type": "deployment_rule"}
                },
                {
                    "text": "重装步兵适合配置在较低至中等高程的防御阵地，坡度不宜过大，以平缓或中等坡度为宜。部署区域植被覆盖度宜为低至中等水平，以保证火力与人员展开空间，同时可利用林缘、矮灌木带作为遮蔽。部署位置通常与居民区保持200-500米缓冲距离，确保火力展开空间，同时避免对居民区造成直接影响。",
                    "metadata": {"unit": "重装步兵", "type": "deployment_rule"}
                },
                {
                    "text": "机械化步兵更适合部署在中等高程的过渡地带，坡度应保持在低至中等坡度范围，以保障装甲车辆通行。植被类型以稀疏林地、草地或农田边缘为宜，避免密林或高密度灌丛阻碍车辆机动。配置位置与居民区的缓冲距离建议控制在300-600米之间，兼顾快速机动与战场安全。",
                    "metadata": {"unit": "机械化步兵", "type": "deployment_rule"}
                },
                {
                    "text": "坦克部队适合部署在低至中等高程的开阔区域，整体坡度应尽量平缓，避免复杂起伏影响机动。植被应以低矮草地、稀疏灌木或已清理区域为主，确保视野与机动空间，避免高大乔木密集分布。配置位置通常要求与居民区保持500-1000米缓冲距离，减少城市地形对装甲单位的限制。",
                    "metadata": {"unit": "坦克部队", "type": "deployment_rule"}
                },
                {
                    "text": "反坦克步兵适合部署在中等至较高高程的伏击位置，坡度可为中等坡度或局部陡坡，便于形成俯射角度。部署区域宜具备较高植被隐蔽度，如林缘、灌木带或起伏草丛，以隐藏阵位并削弱目标发现概率。与居民区之间应保持150-400米缓冲距离，既能隐蔽部署，又不靠近高密度民用区域。",
                    "metadata": {"unit": "反坦克步兵", "type": "deployment_rule"}
                },
                {
                    "text": "自行火炮通常部署在中等高程或背坡地形，坡度以缓坡为主，利于火炮稳定展开。周边植被以低矮草木或零散乔木为宜，既可提供一定遮蔽，又不影响射界与后勤保障。配置位置与居民区应保持600-1000米缓冲距离，以确保安全并减少反侦察风险。",
                    "metadata": {"unit": "自行火炮", "type": "deployment_rule"}
                },
                {
                    "text": "牵引火炮适合配置在相对固定的中低高程阵地，地形坡度应较小且稳定。植被条件宜为低覆盖度或可控清理区域，便于长期部署、火炮调整及补给通行。与居民区的缓冲距离一般控制在400-800米之间，确保持续火力覆盖而不干扰民用区域。",
                    "metadata": {"unit": "牵引火炮", "type": "deployment_rule"}
                },
                {
                    "text": "防空部队适合部署在中等至较高高程位置，坡度以平缓或中等坡度为宜，保证雷达与火力视野。部署区域植被应以低矮或间断分布为主，避免高大连续林冠遮挡探测与射界。部署点与居民区的缓冲距离建议为300-700米，既保证空域覆盖，又降低暴露风险。",
                    "metadata": {"unit": "防空部队", "type": "deployment_rule"}
                },
                {
                    "text": "狙击手适合配置在较高高程制高点，局部坡度可为中等或陡坡，形成良好射界。区域内宜具备高隐蔽度植被条件，如林缘、灌木丛或不规则草木覆盖，以支持隐蔽观察与伪装。配置位置通常与居民区保持50-200米缓冲距离，便于利用城市边缘地形进行隐蔽观察。",
                    "metadata": {"unit": "狙击手", "type": "deployment_rule"}
                },
                {
                    "text": "特种部队适合部署在高程变化明显的复杂地形，坡度可从缓坡到陡坡不等，以增加行动隐蔽性。区域宜具备多样化植被类型，如混合林地、灌木与草地交错分布，以增强掩护与路线选择灵活性。与居民区之间宜保持200-500米缓冲距离，确保渗透行动不暴露于高密度区域。",
                    "metadata": {"unit": "特种部队", "type": "deployment_rule"}
                },
                {
                    "text": "装甲侦察单位适合部署在中低高程区域，整体坡度应较为平缓，便于快速进出。植被条件宜为稀疏分布，既可提供一定遮蔽，又不影响高速机动与观察能力。配置位置与居民区的缓冲距离一般为300-600米，以降低被发现概率。",
                    "metadata": {"unit": "装甲侦察单位", "type": "deployment_rule"}
                },
                {
                    "text": "工兵部队多部署在中低高程的关键节点区域，坡度应相对平缓，方便工程作业。区域内植被覆盖度宜适中或可清理，避免密集林木影响施工、铺设与通行。与居民区保持100-400米缓冲距离，既便于保障基础设施，又避免过度靠近居民区。",
                    "metadata": {"unit": "工兵部队", "type": "deployment_rule"}
                },
                {
                    "text": "后勤保障部队适合部署在低高程、安全区域，坡度应平缓稳定，便于物资运输。植被类型以低矮、通行性良好的草地或人工整备区域为宜，确保运输线路畅通。配置位置通常与居民区保持500-1000米缓冲距离，减少战场干扰风险。",
                    "metadata": {"unit": "后勤保障部队", "type": "deployment_rule"}
                },
                {
                    "text": "指挥单位适合部署在中等高程、地形相对隐蔽的位置，坡度以缓坡或平台地形为宜。周边植被宜形成自然遮蔽，如林缘或中等密度植被带，以增强隐蔽性，同时避免影响通信设施部署。与居民区之间的缓冲距离通常控制在300-600米，在安全与通信效率之间取得平衡。",
                    "metadata": {"unit": "指挥单位", "type": "deployment_rule"}
                },
                {
                    "text": "无人机侦察控制单元适合部署在中高高程区域，坡度应较小，确保设备稳定运行。植被条件宜为低矮或间断分布，避免高大植被干扰起降、信号与视距。与居民区保持400-800米缓冲距离，避免电磁与安全干扰。",
                    "metadata": {"unit": "无人机侦察控制单元", "type": "deployment_rule"}
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
                embedding = self.embedding_model.encode(unit["text"]).tolist()
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
                embedding = self.embedding_model.encode(equipment["text"]).tolist()
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
                embedding = self.embedding_model.encode(unit["text"]).tolist()
                knowledge_coll.add(
                    embeddings=[embedding],
                    documents=[unit["text"]],
                    metadatas=[unit["metadata"]],
                    ids=[f"knowledge_{i}"]
                )
            print(f"已初始化 {len(military_units)} 条军事单位部署规则到knowledge集合")
        
        # 初始化equipment集合
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
                embedding = self.embedding_model.encode(equipment["text"]).tolist()
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
                embedding = self.embedding_model.encode(execution["text"]).tolist()
                executions_coll.add(
                    embeddings=[embedding],
                    documents=[execution["text"]],
                    metadatas=[execution["metadata"]],
                    ids=[f"execution_{i}"]
                )
