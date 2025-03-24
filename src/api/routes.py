import os
import uuid
import time
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from celery.result import AsyncResult
from typing import Optional, Dict, Any
import json

from src.api.schemas import (
    RemoveBackgroundRequest, 
    TaskResponse, 
    TaskStatusResponse, 
    HealthResponse,
    TaskStatus
)
from src.worker.celery_app import app as celery_app
from src.worker.tasks.remove_bg import remove_background
from src.config.logging import api_logger
from src.config import settings

router = APIRouter()

def validate_image_file(file: UploadFile) -> bool:
    """Validate that the uploaded file is an image."""
    allowed_content_types = ["image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_content_types:
        return False
    return True

async def save_upload_file(file: UploadFile) -> str:
    """Save uploaded file to disk and return the path."""
    # Create unique filename
    timestamp = int(time.time())
    unique_id = str(uuid.uuid4())[:8]
    original_filename = file.filename
    extension = os.path.splitext(original_filename)[1]
    
    # Create filename with timestamp and unique ID
    filename = f"upload_{timestamp}_{unique_id}{extension}"
    file_path = os.path.join(settings.TEMP_UPLOAD_DIR, filename)
    
    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    return file_path, original_filename

@router.post("/task", response_model=TaskResponse, status_code=202)
async def create_task(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    request_data: Optional[str] = Form(None)
):
    """
    Create a new background removal task.
    
    - **file**: Image file to remove background from (JPEG or PNG)
    - **request_data**: Optional JSON string with additional parameters
    """
    # Validate file
    if not validate_image_file(file):
        api_logger.error(f"Invalid file type: {file.content_type}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Supported types: JPEG, PNG."
        )
    
    # Parse request data if provided
    request = RemoveBackgroundRequest()
    if request_data:
        try:
            data = json.loads(request_data)
            request = RemoveBackgroundRequest(**data)
        except json.JSONDecodeError:
            api_logger.error(f"Invalid JSON in request_data: {request_data}")
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON in request_data"
            )
        except Exception as e:
            api_logger.error(f"Error parsing request data: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Error parsing request data: {str(e)}"
            )
    
    try:
        # Save uploaded file
        file_path, original_filename = await save_upload_file(file)
        api_logger.info(f"File saved to {file_path}")
        
        # Prepare callback data
        callback_data = None
        if request.callback_url:
            callback_data = {
                "callback_url": str(request.callback_url),
                "callback_auth": request.callback_auth,
                "custom_data": request.custom_data
            }
        
        creation_time = time.time()
        # Submit task to Celery
        task = remove_background.apply_async(
            args=[file_path, original_filename, callback_data],
            queue='gpu',
            kwargs={
                'creation_time': creation_time
            }
        )
        
        api_logger.info(f"Task created with ID: {task.id}")
        
        return TaskResponse(
            task_id=task.id,
            status=TaskStatus.PENDING
        )
    
    except Exception as e:
        api_logger.error(f"Error creating task: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating task: {str(e)}"
        )

@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get the status of a background removal task.
    
    - **task_id**: ID of the task to check
    """
    try:
        # Get task result
        task_result = AsyncResult(task_id, app=celery_app)
        
        # Check if task exists
        if not task_result.state:
            api_logger.error(f"Task not found: {task_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Task not found: {task_id}"
            )
        
        # Map Celery state to our TaskStatus enum
        status_mapping = {
            "PENDING": TaskStatus.PENDING,
            "STARTED": TaskStatus.PROCESSING,
            "SUCCESS": TaskStatus.COMPLETED,
            "FAILURE": TaskStatus.FAILED,
            "REVOKED": TaskStatus.FAILED
        }
        
        status = status_mapping.get(task_result.state, TaskStatus.PENDING)
        
        # Prepare response
        response = TaskStatusResponse(
            task_id=task_id,
            status=status
        )
        
        # Add result URL if task is completed
        if status == TaskStatus.COMPLETED and task_result.result:
            result = task_result.result
            if isinstance(result, dict):
                if "result_url" in result:
                    response.result_url = result["result_url"]
                # Add time information
                if "processing_time" in result:
                    response.processing_time = result["processing_time"]
                if "model_time" in result:
                    response.model_time = result["model_time"]
                if "queue_time" in result:
                    response.queue_time = result["queue_time"]
        
        # Add error if task failed
        if status == TaskStatus.FAILED:
            if task_result.result:
                if isinstance(task_result.result, Exception):
                    response.error = str(task_result.result)
                elif isinstance(task_result.result, dict):
                    if "error" in task_result.result:
                        response.error = task_result.result["error"]
                    # Add time information for failed tasks
                    if "processing_time" in task_result.result:
                        response.processing_time = task_result.result["processing_time"]
                    if "model_time" in task_result.result:
                        response.model_time = task_result.result["model_time"]
                    if "queue_time" in task_result.result:
                        response.queue_time = task_result.result["queue_time"]
            else:
                response.error = "Unknown error"
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"Error getting task status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting task status: {str(e)}"
        )

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check the health of the service.
    """
    try:
        # Check Celery connection
        celery_status = "healthy"
        try:
            # Try to ping Celery
            celery_ping = celery_app.control.ping(timeout=1.0)
            if not celery_ping:
                celery_status = "unhealthy"
        except Exception:
            celery_status = "unhealthy"
        
        # Check Redis connection
        redis_status = "healthy"
        try:
            # Use Celery's connection to check Redis
            if celery_status == "unhealthy":
                redis_status = "unknown"
        except Exception:
            redis_status = "unhealthy"
        
        # Overall status
        overall_status = "healthy"
        if celery_status != "healthy" or redis_status != "healthy":
            overall_status = "degraded"
        
        return HealthResponse(
            status=overall_status,
            version="1.0.0",  # This should be fetched from a version file in a real app
            components={
                "api": "healthy",
                "worker": celery_status,
                "redis": redis_status
            }
        )
    except Exception as e:
        api_logger.error(f"Error in health check: {e}")
        return HealthResponse(
            status="unhealthy",
            version="1.0.0",
            components={
                "api": "unhealthy",
                "worker": "unknown",
                "redis": "unknown"
            }
        )
