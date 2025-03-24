import os
import argparse
import uvicorn
import subprocess
import signal
import sys
import time
from pathlib import Path
import redis
from botocore.exceptions import ClientError

from src.config import settings
from src.utils.s3 import S3Client

def get_gpu_count():
    """Get the number of available GPUs."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            return len(result.stdout.strip().split("\n"))
    except Exception:
        pass
    return 0

def start_api(host, port, reload):
    """Start the FastAPI server."""
    print(f"Starting API server on {host}:{port}")
    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        reload=reload
    )

def start_worker(concurrency, loglevel, gpu_index=None):
    """Start the Celery worker with optional GPU assignment."""
    print(f"Starting Celery worker with concurrency {concurrency}")
    worker_cmd = [
        "celery",
        "-A", "src.worker.celery_app",
        "worker",
        "--loglevel", loglevel,
        "--concurrency", str(concurrency)
    ]
    
    if gpu_index is not None:
        worker_cmd.extend(["-Q", "gpu"])
        os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_index)
    
    worker_process = subprocess.Popen(worker_cmd)
    return worker_process

def start_all(host, port, concurrency, loglevel, reload):
    """Start API and worker(s) based on GPU availability."""
    gpu_count = get_gpu_count()
    worker_processes = []
    
    if gpu_count > 0:
        print(f"Detected {gpu_count} GPUs, starting {gpu_count} workers")
        for i in range(gpu_count):
            worker_processes.append(start_worker(concurrency, loglevel, gpu_index=i))
    else:
        print("No GPU detected, starting single CPU worker")
        worker_processes.append(start_worker(concurrency, loglevel))
    
    try:
        start_api(host, port, reload)
    finally:
        print("Stopping workers...")
        for p in worker_processes:
            p.terminate()
            p.wait(timeout=5)

def check_redis_connection():
    """Check if Redis is running and accessible."""
    print("Checking Redis connection...")
    try:
        r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        r.ping()
        print("✅ Redis connection successful!")
        return True
    except redis.ConnectionError as e:
        print(f"❌ Redis connection failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Redis check failed with unexpected error: {e}")
        return False

def check_s3_connection():
    """Check if S3 is accessible and bucket exists."""
    print("Checking S3 connection...")
    try:
        # Skip if S3 settings are not configured
        if not settings.S3_ACCESS_KEY or not settings.S3_SECRET_KEY:
            print("⚠️ S3 not configured, skipping check")
            return True
            
        s3_client = S3Client()
        # Try to list objects to verify connection and permissions
        s3_client.client.list_objects_v2(Bucket=s3_client.bucket_name, MaxKeys=1)
        print(f"✅ S3 connection successful! Bucket '{s3_client.bucket_name}' is accessible.")
        return True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        print(f"❌ S3 connection failed: {e}")
        if error_code == 'NoSuchBucket':
            print(f"   Bucket '{settings.S3_BUCKET_NAME}' does not exist.")
        return False
    except Exception as e:
        print(f"❌ S3 check failed with unexpected error: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Background Removal Service locally")
    parser.add_argument("--api-only", action="store_true", help="Run only the API server")
    parser.add_argument("--worker-only", action="store_true", help="Run only the Celery worker")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the API server")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the API server")
    parser.add_argument("--concurrency", type=int, default=1, help="Worker concurrency")
    parser.add_argument("--loglevel", default="info", help="Log level for Celery worker")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--skip-checks", action="store_true", help="Skip dependency checks")
    
    args = parser.parse_args()
    
    # Create required directories
    Path("logs").mkdir(exist_ok=True)
    
    # Check dependencies unless --skip-checks is specified
    if not args.skip_checks:
        print("\n=== Checking dependencies ===")
        redis_ok = check_redis_connection()
        s3_ok = check_s3_connection()
        
        if not redis_ok:
            print("\n⚠️ Redis check failed. The service may not function correctly.")
            user_input = input("Do you want to continue anyway? (y/n): ").lower()
            if user_input != 'y':
                print("Exiting...")
                sys.exit(1)
        
        if not s3_ok and settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY:
            print("\n⚠️ S3 check failed. File uploads may not work correctly.")
            user_input = input("Do you want to continue anyway? (y/n): ").lower()
            if user_input != 'y':
                print("Exiting...")
                sys.exit(1)
        
        print("\n=== All checks completed ===\n")
    
    if args.api_only:
        start_api(args.host, args.port, args.reload)
    elif args.worker_only:
        worker_process = start_worker(args.concurrency, args.loglevel)
        
        # Handle termination signals
        def signal_handler(sig, frame):
            print("Stopping worker...")
            worker_process.terminate()
            worker_process.wait(timeout=5)
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep main thread alive
        while True:
            time.sleep(1)
    else:
        start_all(args.host, args.port, args.concurrency, args.loglevel, args.reload)
