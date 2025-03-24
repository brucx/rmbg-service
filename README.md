# AI Background Removal Service

一个基于 Celery 和 GPU 加速的异步背景移除服务，支持将结果上传至 S3 并通过回调接口通知处理状态。

## 项目概述

该服务使用 AI 模型（U2Net）来移除图像背景，并提供以下功能：

- 通过 REST API 接收图像处理请求
- 使用 Celery 进行异步任务处理
- 利用 GPU 加速 AI 推理过程
- 将处理结果上传至 S3 存储
- 支持回调通知处理结果
- 提供任务状态查询接口

## 系统架构

系统由以下主要组件组成：

1. **API 服务**：接收用户请求，创建后台任务
2. **Celery Worker**：执行背景移除任务
3. **Redis**：作为 Celery 的消息代理和结果后端
4. **AI 模型**：使用 ONNX 格式的 U2Net 模型进行背景移除
5. **S3 存储**：存储处理结果
6. **回调服务**：通知任务完成状态

## 安装与配置

### 前置条件

- Python 3.8+
- Redis 服务器
- NVIDIA GPU (推荐用于生产环境)
- S3 兼容的存储服务 (AWS S3, MinIO 等)

### 环境变量配置

创建 `.env` 文件并配置以下环境变量：

```
# API 配置
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=False

# Celery 配置
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_WORKER_CONCURRENCY=1

# S3 配置
S3_ENDPOINT=https://your-s3-endpoint.com  # 可选，用于 MinIO 等
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_BUCKET_NAME=rmbg-results
S3_REGION=us-east-1
S3_USE_SSL=True

# 回调配置
CALLBACK_ENABLED=True
CALLBACK_URL=https://your-callback-url.com
CALLBACK_AUTH_TOKEN=your-auth-token

# 模型配置
MODEL_PATH=models/u2net.onnx
DEVICE=cuda  # 使用 CPU 时设置为 cpu
BATCH_SIZE=1
IMG_SIZE=320

# 存储配置
TEMP_UPLOAD_DIR=/tmp/rmbg-uploads
RESULT_DIR=/tmp/rmbg-results
```

### 安装依赖

```bash
pip install -r requirements.txt
```

### 下载模型

在项目根目录创建 `models` 文件夹，并下载 U2Net 模型：

```bash
mkdir -p models
# 下载 U2Net ONNX 模型
wget -O models/u2net.onnx https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx
```

## 运行服务

### 本地开发环境

启动完整服务（API 和 Worker）：

```bash
python run_local.py
```

仅启动 API 服务：

```bash
python run_local.py --api-only
```

仅启动 Worker 服务：

```bash
python run_local.py --worker-only
```

### 使用 Docker Compose

```bash
docker-compose up -d
```

## API 接口

### 创建背景移除任务

```
POST /task
```

请求格式：`multipart/form-data`

参数：
- `file`: 要处理的图像文件（JPEG 或 PNG）
- `request_data`: 可选的 JSON 字符串，包含回调配置等信息

示例请求：

```bash
curl -X POST http://localhost:8000/task \
  -F "file=@image.jpg" \
  -F 'request_data={"callback_url": "https://example.com/callback", "callback_auth": "Bearer token123", "custom_data": {"user_id": "123"}}'
```

响应示例：

```json
{
  "task_id": "12345678-1234-5678-1234-567812345678",
  "status": "pending"
}
```

### 查询任务状态

```
GET /task/{task_id}
```

响应示例：

```json
{
  "task_id": "12345678-1234-5678-1234-567812345678",
  "status": "completed",
  "result_url": "https://s3-bucket.amazonaws.com/rmbg-results/image_nobg.png"
}
```

### 健康检查

```
GET /health
```

响应示例：

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "api": "healthy",
    "worker": "healthy",
    "redis": "healthy"
  }
}
```

## 回调通知

当任务状态变更时，系统会向配置的回调 URL 发送 POST 请求，包含以下信息：

```json
{
  "task_id": "12345678-1234-5678-1234-567812345678",
  "status": "completed",
  "result_url": "https://s3-bucket.amazonaws.com/rmbg-results/image_nobg.png",
  "custom_data": {
    "user_id": "123"
  }
}
```

## Docker 部署

项目包含以下 Docker 配置文件：

- `Dockerfile.api`: API 服务的 Docker 配置
- `Dockerfile.worker`: Worker 服务的 Docker 配置
- `docker-compose.yml`: 本地开发的 Docker Compose 配置

## 项目结构

```
src/
├── api/                      # API服务
│   ├── __init__.py
│   ├── app.py                # API入口点
│   ├── routes.py             # API路由
│   └── schemas.py            # 请求/响应模型
├── worker/                   # Worker服务
│   ├── __init__.py
│   ├── celery_app.py         # Celery配置
│   ├── tasks/
│   │   ├── __init__.py
│   │   └── remove_bg.py      # 背景移除任务
│   └── models/
│       ├── __init__.py
│       └── bg_removal.py     # AI模型封装
├── utils/                    # 工具类
│   ├── __init__.py
│   ├── s3.py                 # S3操作工具
│   └── callbacks.py          # 回调工具
├── config/                   # 配置
│   ├── __init__.py
│   ├── settings.py           # 全局配置
│   └── logging.py            # 日志配置
```

## 性能优化

- 使用 GPU 加速推理过程
- 通过调整 `CELERY_WORKER_CONCURRENCY` 控制并发任务数
- 优化图像处理流程，减少内存占用
- 使用异步任务处理，避免阻塞 API 服务

## 故障排除

1. **Worker 无法启动**
   - 检查 Redis 服务是否正常运行
   - 确认 Celery 配置正确

2. **GPU 不可用**
   - 检查 CUDA 安装
   - 确认 `onnxruntime-gpu` 安装正确
   - 将 `DEVICE` 环境变量设置为 `cpu` 以使用 CPU 推理

3. **S3 上传失败**
   - 检查 S3 凭证和权限
   - 确认网络连接正常

## 许可证

MIT
