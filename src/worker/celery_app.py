from celery import Celery
from src.config import settings
from src.config.logging import worker_logger

# Initialize Celery app
app = Celery('rmbg_worker')

# Configure Celery
app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY
)

# Import worker initialization module to register signal handlers
import src.worker.worker_init

# Import tasks explicitly to ensure they're registered
import src.worker.tasks.remove_bg

# Auto-discover tasks
app.autodiscover_tasks(['src.worker.tasks'])

worker_logger.info("Celery worker initialized")

@app.task(bind=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    worker_logger.info(f'Request: {self.request!r}')
    return 'Hello from Celery!'
