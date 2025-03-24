import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# API Settings
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8000'))
API_DEBUG = os.getenv('API_DEBUG', 'False').lower() == 'true'

# Celery Settings
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_WORKER_CONCURRENCY = int(os.getenv('CELERY_WORKER_CONCURRENCY', '1'))

# S3 Settings
S3_ENDPOINT = os.getenv('S3_ENDPOINT', '')
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY', '')
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY', '')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'rmbg-results')
S3_REGION = os.getenv('S3_REGION', 'us-east-1')
S3_USE_SSL = os.getenv('S3_USE_SSL', 'True').lower() == 'true'

# Callback Settings
CALLBACK_ENABLED = os.getenv('CALLBACK_ENABLED', 'True').lower() == 'true'
CALLBACK_URL = os.getenv('CALLBACK_URL', '')
CALLBACK_AUTH_TOKEN = os.getenv('CALLBACK_AUTH_TOKEN', '')

# Model Settings
MODEL_PATH = os.getenv('MODEL_PATH', 'models/u2net.onnx')
DEVICE = os.getenv('DEVICE', 'cuda')  # 'cuda' or 'cpu'
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '1'))
IMG_SIZE = int(os.getenv('IMG_SIZE', '320'))

# Storage Settings
TEMP_UPLOAD_DIR = os.getenv('TEMP_UPLOAD_DIR', '/tmp/rmbg-uploads')
RESULT_DIR = os.getenv('RESULT_DIR', '/tmp/rmbg-results')

# Create directories if they don't exist
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)
