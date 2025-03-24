import os
import uuid
import time
from celery import states
from datetime import datetime
from src.worker.celery_app import app
from src.worker.models.bg_removal import BackgroundRemovalModel
from src.utils.s3 import S3Client
from src.utils.callbacks import CallbackClient
from src.config.logging import worker_logger
from src.config import settings

@app.task(bind=True, name='remove_background')
def remove_background(self, image_path, original_filename=None, callback_data=None, creation_time=None):
    """
    Celery task to remove background from an image.
    
    Args:
        self: Task instance
        image_path (str): Path to the input image
        original_filename (str, optional): Original filename of the uploaded image
        callback_data (dict, optional): Additional data to include in callback
        creation_time (float, optional): Timestamp when the task was created
        
    Returns:
        dict: Task result information
    """
    task_id = self.request.id
    start_time = time.time()  # 记录开始时间
    
    # 计算队列等待时间
    queue_time = round(start_time - creation_time, 3) if creation_time is not None else None
    
    worker_logger.info(f"Starting background removal task {task_id} for image {image_path} (queue wait: {queue_time}s)")
    
    # Initialize clients
    s3_client = S3Client()
    callback_client = CallbackClient()
    
    # Update task state to STARTED
    self.update_state(state=states.STARTED, meta={'status': 'processing'})
    
    # Send callback for processing status
    if callback_data:
        callback_client.send_callback(
            task_id=task_id,
            status='processing',
            **callback_data
        )
    
    try:
        # Generate output paths
        if not original_filename:
            original_filename = os.path.basename(image_path)
        
        filename_without_ext = os.path.splitext(original_filename)[0]
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        
        output_filename = f"{filename_without_ext}_nobg_{timestamp}_{unique_id}.png"
        output_path = os.path.join(settings.RESULT_DIR, output_filename)
        
        # Get the singleton model instance instead of creating a new one
        model = BackgroundRemovalModel.get_instance()
        
        # Process image
        worker_logger.info(f"Processing image {image_path} with model")
        model_start_time = time.time()  # 记录模型处理开始时间
        success = model.remove_background(
            image_path=image_path,
            output_path=output_path
        )
        model_processing_time = time.time() - model_start_time  # 计算模型处理时间
        
        if not success:
            raise Exception("Failed to process image with model")
        
        # Check if S3 credentials are configured
        result_url = None
        s3_configured = settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY
        
        if s3_configured:
            # Upload result to S3
            worker_logger.info(f"Uploading result to S3: {output_path}")
            result_url = s3_client.upload_file(
                file_path=output_path,
                object_name=f"results/{output_filename}",
                content_type="image/png"
            )
        else:
            # For local development, just use the local file path
            worker_logger.info(f"S3 not configured, using local file path: {output_path}")
            result_url = f"file://{output_path}"
        
        # 计算总处理时间
        total_processing_time = time.time() - start_time
        
        # Send success callback
        result = {
            'status': 'completed',
            'result_url': result_url,
            'original_filename': original_filename,
            'output_filename': output_filename,
            'processing_time': round(total_processing_time, 3),  # 总处理时间（秒）
            'model_time': round(model_processing_time, 3),  # 模型处理时间（秒）
            'queue_time': queue_time  # 队列等待时间（秒）
        }
        
        if callback_data:
            callback_client.send_callback(
                task_id=task_id,
                status='completed',
                result_url=result_url,
                processing_time=round(total_processing_time, 3),
                model_time=round(model_processing_time, 3),
                queue_time=queue_time,
                **callback_data
            )
        
        worker_logger.info(f"Background removal task {task_id} completed successfully in {round(total_processing_time, 3)}s (model: {round(model_processing_time, 3)}s, queue: {queue_time}s)")
        return result
        
    except Exception as e:
        error_message = f"Error in background removal task: {str(e)}"
        worker_logger.error(error_message)
        
        # 计算失败时的处理时间
        error_time = time.time() - start_time
        
        # Send failure callback
        if callback_data:
            callback_client.send_callback(
                task_id=task_id,
                status='failed',
                error=error_message,
                processing_time=round(error_time, 3),
                queue_time=queue_time,
                **callback_data
            )
        
        # Update task state to FAILURE
        self.update_state(state=states.FAILURE, meta={
            'status': 'failed',
            'error': error_message,
            'processing_time': round(error_time, 3),
            'queue_time': queue_time
        })
        
        # Re-raise exception to mark task as failed
        raise
    finally:
        # Clean up temporary files
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                worker_logger.info(f"Removed temporary input file: {image_path}")
            
            # Don't remove output file in local development mode
            # if 'output_path' in locals() and os.path.exists(output_path):
            #    os.remove(output_path)
            #    worker_logger.info(f"Removed temporary output file: {output_path}")
        except Exception as e:
            worker_logger.error(f"Error cleaning up temporary files: {e}")
