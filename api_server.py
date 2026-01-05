from fastapi import FastAPI, HTTPException  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import JSONResponse, FileResponse  # type: ignore
from pydantic import BaseModel, Field  # type: ignore
from typing import Dict, Any, Optional, List
import uvicorn  # type: ignore
import threading
from pathlib import Path
import sys
import logging
import os
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from orchestrator import Orchestrator
    from context_manager import ContextManager
    from config import PATHS
    from context.kag.schema import COLLECTION_TO_ENTITY_TYPE
except ImportError:
    BASE_DIR_PARENT = BASE_DIR.parent
    if str(BASE_DIR_PARENT) not in sys.path:
        sys.path.insert(0, str(BASE_DIR_PARENT))
    from orchestrator import Orchestrator
    from context_manager import ContextManager
    from config import PATHS
    from context.kag.schema import COLLECTION_TO_ENTITY_TYPE

app = FastAPI(
    title="空地智能体API服务",
    description="空地计算智能体系统的API接口",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 延迟初始化，避免启动时阻塞
orchestrator = None
context_manager = None

def get_orchestrator():
    """获取Orchestrator实例（延迟初始化）"""
    global orchestrator
    if orchestrator is None:
        orchestrator = Orchestrator()
    return orchestrator

def get_context_manager():
    """获取ContextManager实例（延迟初始化）"""
    global context_manager
    if context_manager is None:
        context_manager = ContextManager()
    return context_manager

class TaskRequest(BaseModel):
    task: str = Field(..., description="任务描述")

class PlanRequest(BaseModel):
    task: str = Field(..., description="任务描述")

class ReplanRequest(BaseModel):
    plan: Dict[str, Any] = Field(..., description="原计划")
    feedback: str = Field(..., description="用户反馈意见")

class ExecuteRequest(BaseModel):
    plan: Dict[str, Any] = Field(..., description="执行计划")

class TaskResponse(BaseModel):
    success: bool
    result: Dict[str, Any]
    message: Optional[str] = None

class KnowledgeAddRequest(BaseModel):
    text: str = Field(..., description="文本内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    collection: str = Field(default="knowledge", description="集合名称")

@app.get("/")
async def root():
    return {
        "service": "空地智能体API服务",
        "version": "1.0.0",
        "endpoints": {
            "/api/plan": "POST - 生成计划",
            "/api/replan": "POST - 根据反馈重新规划",
            "/api/execute": "POST - 执行计划",
            "/api/task": "POST - 提交任务（完整流程）",
            "/api/tools": "GET - 获取工具列表",
            "/api/collections": "GET - 获取所有集合信息",
            "/api/knowledge": "GET - 获取集合数据, POST - 添加数据",
            "/api/knowledge/{id}": "DELETE - 删除记录",
            "/api/knowledge/update": "PUT - 批量更新knowledge集合",
            "/api/results": "GET - 获取所有结果文件列表",
            "/api/results/{filename}": "GET - 获取特定结果文件内容",
            "/docs": "GET - API文档"
        }
    }

@app.post("/api/plan", response_model=TaskResponse)
async def generate_plan(request: PlanRequest):
    try:
        result = get_orchestrator().generate_plan(request.task)
        return TaskResponse(
            success=result.get("success", False),
            result=result,
            message="计划生成完成"
        )
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"生成计划错误: {str(e)}")
        logger.error(error_detail)

        error_msg = str(e)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."

        raise HTTPException(status_code=500, detail=f"生成计划时出错: {error_msg}")

@app.post("/api/replan", response_model=TaskResponse)
async def replan_with_feedback(request: ReplanRequest):
    try:
        import traceback
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"收到重新规划请求，反馈: {request.feedback[:100]}")

        result = get_orchestrator().replan_with_feedback(request.plan, request.feedback)

        logger.info("重新规划成功")
        return TaskResponse(
            success=result.get("success", False),
            result=result,
            message="重新规划完成"
        )
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)

        error_detail = traceback.format_exc()
        logger.error(f"重新规划错误: {str(e)}")
        logger.error(error_detail)

        error_msg = str(e)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."

        raise HTTPException(
            status_code=500,
            detail=f"重新规划时出错: {error_msg}"
        )

@app.post("/api/execute", response_model=TaskResponse)
async def execute_plan(request: ExecuteRequest):
    try:
        result = get_orchestrator().execute_plan(request.plan)
        return TaskResponse(
            success=result.get("success", False),
            result=result,
            message="执行完成" if result.get("success") else "执行失败"
        )
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"执行计划错误: {str(e)}")
        logger.error(error_detail)

        error_msg = str(e)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."

        raise HTTPException(status_code=500, detail=f"执行计划时出错: {error_msg}")

@app.post("/api/task", response_model=TaskResponse)
async def submit_task(request: TaskRequest):
    try:
        result = get_orchestrator().execute_task(request.task)
        return TaskResponse(
            success=result.get("success", False),
            result=result,
            message="任务执行完成" if result.get("success") else "任务执行失败"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行任务时出错: {str(e)}")

@app.get("/api/tools")
async def get_tools():
    tools = {}
    for name, tool in get_orchestrator().work_agent.tools.items():
        tools[name] = {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters
        }
    return {"tools": tools}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/collections")
async def get_collections():
    """获取所有集合的基本信息"""
    try:
        collections_info = {}
        for collection_name in ["knowledge", "equipment"]:
            try:
                entity_type = COLLECTION_TO_ENTITY_TYPE.get(collection_name, "MilitaryUnit")
                entities = get_context_manager().kag.get_entities_by_type(entity_type)
                collections_info[collection_name] = {
                    "name": collection_name,
                    "count": len(entities)
                }
            except Exception as e:
                collections_info[collection_name] = {
                    "name": collection_name,
                    "count": 0,
                    "error": str(e)
                }
        return {"success": True, "collections": collections_info}
    except Exception as e:
        logger.error(f"获取集合信息失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取集合信息失败: {str(e)}")

@app.get("/api/knowledge")
async def get_knowledge(collection: str = "knowledge"):
    """获取指定集合的所有数据"""
    try:
        entity_type = COLLECTION_TO_ENTITY_TYPE.get(collection, "MilitaryUnit")
        entities = get_context_manager().kag.get_entities_by_type(entity_type)

        items = []
        for entity in entities:
            items.append({
                "id": entity["id"],
                "text": entity.get("text", ""),
                "metadata": entity.get("properties", {})
            })

        return {
            "success": True,
            "collection": collection,
            "count": len(items),
            "items": items
        }
    except Exception as e:
        logger.error(f"获取{collection}集合数据失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")

@app.post("/api/knowledge")
async def add_knowledge(request: KnowledgeAddRequest):
    """添加数据到指定集合"""
    try:
        collection = request.collection
        entity_type = COLLECTION_TO_ENTITY_TYPE.get(collection, "MilitaryUnit")
        
        import time
        from uuid import uuid4
        timestamp_ms = int(time.time() * 1000)
        unique_suffix = uuid4().hex[:8]
        new_id = f"{collection}_{timestamp_ms}_{unique_suffix}"

        properties = request.metadata.copy()
        properties["text"] = request.text

        get_context_manager().kag.add_entity(
            entity_type=entity_type,
            entity_id=new_id,
            properties=properties,
            text=request.text
        )

        logger.info(f"成功添加数据到{collection}集合，ID: {new_id}")

        return {
            "success": True,
            "message": f"数据已添加到{collection}集合",
            "id": new_id
        }
    except Exception as e:
        logger.error(f"添加数据到{collection}集合失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"添加数据失败: {str(e)}")

@app.delete("/api/knowledge/{item_id}")
async def delete_knowledge(item_id: str, collection: str = "knowledge"):
    """删除指定集合中的特定记录"""
    try:
        entity = get_context_manager().kag.get_entity(item_id)
        if entity is None:
            raise HTTPException(status_code=404, detail=f"记录 {item_id} 不存在")

        get_context_manager().kag.delete_entity(item_id)

        logger.info(f"成功从{collection}集合删除记录: {item_id}")

        return {
            "success": True,
            "message": f"记录 {item_id} 已从{collection}集合删除"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从{collection}集合删除记录失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除记录失败: {str(e)}")

@app.delete("/api/knowledge/clear/{collection}")
async def clear_collection(collection: str):
    """清空指定集合的所有记录"""
    try:
        allowed_collections = ["knowledge", "equipment"]
        if collection not in allowed_collections:
            raise HTTPException(
                status_code=400, 
                detail=f"不允许清空{collection}集合。只允许清空: {', '.join(allowed_collections)}"
            )

        entity_type = COLLECTION_TO_ENTITY_TYPE.get(collection, "MilitaryUnit")
        entities = get_context_manager().kag.get_entities_by_type(entity_type)

        if entities:
            count = len(entities)
            for entity in entities:
                get_context_manager().kag.delete_entity(entity["id"])
            logger.info(f"成功清空{collection}集合，共删除{count}条记录")
            return {
                "success": True,
                "message": f"{collection}集合已清空，共删除{count}条记录",
                "count": count
            }
        else:
            return {
                "success": True,
                "message": f"{collection}集合已经是空的",
                "count": 0
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清空{collection}集合失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"清空集合失败: {str(e)}")

@app.put("/api/knowledge/update")
async def update_knowledge_base():
    """批量更新knowledge集合（重新初始化军事单位部署规则）"""
    try:
        count = get_context_manager().update_knowledge_base()
        logger.info(f"成功更新knowledge集合，共{count}条记录")

        return {
            "success": True,
            "message": f"knowledge集合已更新",
            "count": count
        }
    except Exception as e:
        logger.error(f"更新knowledge集合失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新knowledge集合失败: {str(e)}")

@app.get("/api/results")
async def get_results_list():
    """获取所有结果文件列表"""
    try:
        result_dir = PATHS["result_dir"]
        if not result_dir.exists():
            return {
                "success": True,
                "results": [],
                "count": 0
            }

        result_files = list(result_dir.glob("*.geojson"))
        result_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        results = []
        for file_path in result_files:
            stat = file_path.stat()
            results.append({
                "filename": file_path.name,
                "size": stat.st_size,
                "modified_time": stat.st_mtime,
                "modified_time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            })

        return {
            "success": True,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"获取结果文件列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取结果文件列表失败: {str(e)}")

@app.get("/api/results/{filename}")
async def get_result_file(filename: str):
    """获取特定结果文件内容（GeoJSON）"""
    try:
        result_dir = PATHS["result_dir"]
        file_path = result_dir / filename

        if not file_path.resolve().is_relative_to(result_dir.resolve()):
            raise HTTPException(status_code=403, detail="访问被拒绝")

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"文件 {filename} 不存在")

        if not filename.endswith('.geojson'):
            raise HTTPException(status_code=400, detail="只支持GeoJSON文件")

        return FileResponse(
            path=str(file_path),
            media_type="application/geo+json",
            filename=filename
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取结果文件失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取结果文件失败: {str(e)}")

def run_api_server(port: int = 8000):
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")