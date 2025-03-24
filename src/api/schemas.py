from pydantic import BaseModel, Field, validator, AnyUrl
from typing import Optional, Dict, Any, List
from enum import Enum

class TaskStatus(str, Enum):
    """Enum for task status values."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class RemoveBackgroundRequest(BaseModel):
    """Request model for background removal task."""
    callback_url: Optional[AnyUrl] = Field(
        None, 
        description="URL to receive callback when task is completed"
    )
    callback_auth: Optional[str] = Field(
        None, 
        description="Authentication token for callback"
    )
    custom_data: Optional[Dict[str, Any]] = Field(
        None, 
        description="Custom data to include in callback"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "callback_url": "https://example.com/callback",
                "callback_auth": "Bearer token123",
                "custom_data": {"user_id": "123", "order_id": "456"}
            }
        }

class TaskResponse(BaseModel):
    """Response model for task creation."""
    task_id: str = Field(..., description="ID of the created task")
    status: TaskStatus = Field(..., description="Current status of the task")
    
    class Config:
        schema_extra = {
            "example": {
                "task_id": "12345678-1234-5678-1234-567812345678",
                "status": "pending"
            }
        }

class TaskStatusResponse(BaseModel):
    """Response model for task status."""
    task_id: str = Field(..., description="ID of the task")
    status: TaskStatus = Field(..., description="Current status of the task")
    result_url: Optional[str] = Field(
        None, 
        description="URL to the result image (only present if status is completed)"
    )
    error: Optional[str] = Field(
        None, 
        description="Error message (only present if status is failed)"
    )
    processing_time: Optional[float] = Field(
        None,
        description="Total processing time in seconds"
    )
    model_time: Optional[float] = Field(
        None,
        description="Model inference time in seconds"
    )
    queue_time: Optional[float] = Field(
        None,
        description="Time spent waiting in queue before processing"
    )
    
    @validator('result_url')
    def validate_url(cls, v):
        if v is None:
            return v
        # Allow localhost URLs and regular URLs
        if v.startswith(('http://', 'https://')):
            return v
        raise ValueError('URL must start with http:// or https://')
    
    class Config:
        schema_extra = {
            "example": {
                "task_id": "12345678-1234-5678-1234-567812345678",
                "status": "completed",
                "result_url": "https://example.com/results/image.png",
                "processing_time": 2.345,
                "model_time": 1.234,
                "queue_time": 0.123
            }
        }

class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Service version")
    components: Dict[str, str] = Field(..., description="Status of service components")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "components": {
                    "api": "healthy",
                    "worker": "healthy",
                    "redis": "healthy"
                }
            }
        }

class ErrorResponse(BaseModel):
    """Response model for errors."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    
    class Config:
        schema_extra = {
            "example": {
                "error": "Bad Request",
                "detail": "Invalid file format. Only JPEG and PNG are supported."
            }
        }
