#!/bin/bash

# 启动脚本：启动4个Celery worker，每个worker分配不同的GPU

# 确保脚本在出错时退出
set -e

# 项目根目录
PROJECT_DIR=$(dirname "$0")
cd "$PROJECT_DIR"

# 创建日志目录
mkdir -p logs

echo "正在启动4个Celery worker，每个worker使用不同的GPU..."

# 启动4个worker，每个worker有不同的名称和环境变量
# worker1 - GPU 0
CELERY_WORKER_NAME="worker1" CUDA_VISIBLE_DEVICES="0" celery -A src.worker.celery_app worker --loglevel=INFO --concurrency=1 --hostname=worker1@%h --logfile=logs/worker1.log --detach

# worker2 - GPU 1
CELERY_WORKER_NAME="worker2" CUDA_VISIBLE_DEVICES="1" celery -A src.worker.celery_app worker --loglevel=INFO --concurrency=1 --hostname=worker2@%h --logfile=logs/worker2.log --detach

# worker3 - GPU 2
CELERY_WORKER_NAME="worker3" CUDA_VISIBLE_DEVICES="2" celery -A src.worker.celery_app worker --loglevel=INFO --concurrency=1 --hostname=worker3@%h --logfile=logs/worker3.log --detach

# worker4 - GPU 3
CELERY_WORKER_NAME="worker4" CUDA_VISIBLE_DEVICES="3" celery -A src.worker.celery_app worker --loglevel=INFO --concurrency=1 --hostname=worker4@%h --logfile=logs/worker4.log --detach

echo "所有worker已启动，查看日志目录logs获取详细信息"
echo "使用 'celery -A src.worker.celery_app status' 检查worker状态"

# 显示worker状态
echo "当前worker状态:"
celery -A src.worker.celery_app status
