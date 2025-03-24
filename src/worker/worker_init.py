from celery.signals import worker_init, worker_process_init
from src.worker.models.bg_removal import BackgroundRemovalModel
from src.config.logging import worker_logger
import os

@worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Initialize resources when each worker process starts.
    This is called for each worker process (based on concurrency setting).
    """
    # Get worker ID from environment variable or process ID
    worker_id = get_worker_id()
    worker_logger.info(f"Initializing worker process {worker_id} - preloading model to GPU")
    
    # Preload model to GPU with specific worker ID
    BackgroundRemovalModel.get_instance(worker_id=worker_id)
    worker_logger.info(f"Model preloaded successfully for worker {worker_id}")

def get_worker_id():
    """
    Get the worker ID from environment variables or generate one based on process ID.
    
    Returns:
        int: Worker ID
    """
    # Try to get worker ID from Celery worker name
    worker_name = os.environ.get('CELERY_WORKER_NAME', '')
    if worker_name:
        # Extract worker number from name (e.g., "worker1" -> 1)
        try:
            worker_id = int(''.join(filter(str.isdigit, worker_name)))
            return worker_id
        except ValueError:
            pass
    
    # Try to get worker ID from process ID (fallback)
    try:
        # Use last digit of process ID as worker ID
        worker_id = os.getpid() % 10
        return worker_id
    except:
        # Default to 0 if all else fails
        return 0
