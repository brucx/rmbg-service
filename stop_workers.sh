#!/bin/bash

# 停止脚本：停止所有Celery worker

echo "正在停止所有Celery worker..."

# 使用celery控制命令停止所有worker
celery -A src.worker.celery_app control shutdown

# 确保所有worker进程都已停止
echo "等待worker进程完全停止..."
sleep 3

# 检查是否有残留的worker进程，如果有则强制终止
WORKER_PIDS=$(pgrep -f "celery.*worker")
if [ ! -z "$WORKER_PIDS" ]; then
    echo "强制终止残留的worker进程..."
    echo $WORKER_PIDS | xargs kill -9
fi

echo "所有worker已停止"
