from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import os

from src.api.routes import router
from src.config.logging import api_logger
from src.config import settings

# Create FastAPI app
app = FastAPI(
    title="Background Removal API",
    description="API for removing backgrounds from images using AI",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be restricted
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Get client IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0]
    else:
        client_ip = request.client.host
    
    # Log request
    api_logger.info(f"Request: {request.method} {request.url.path} from {client_ip}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log response
    api_logger.info(
        f"Response: {request.method} {request.url.path} "
        f"status_code={response.status_code} "
        f"process_time={process_time:.4f}s"
    )
    
    return response

# Add global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    api_logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": str(exc)}
    )

# Include API routes
app.include_router(router)

# Create required directories
os.makedirs(settings.TEMP_UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.RESULT_DIR, exist_ok=True)

# Startup event
@app.on_event("startup")
async def startup_event():
    api_logger.info("API starting up")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    api_logger.info("API shutting down")
