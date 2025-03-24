#!/usr/bin/env python3
"""
Load testing script for rmbg-service.
Sends 100 requests with test.jpg using 10 concurrent workers and tracks task completion status.
"""

import asyncio
import aiohttp
import time
import json
from collections import Counter, defaultdict
from datetime import datetime
import os
from typing import Dict, List, Any

# Configuration
TOTAL_REQUESTS = 100
CONCURRENCY = 10
IMAGE_PATH = "test.jpg"
API_URL = "http://localhost:8000"  # Change this to your API URL if different

# Statistics
task_statuses = {}
processing_times = defaultdict(list)
start_time = None
end_time = None

async def submit_task(session: aiohttp.ClientSession, request_id: int) -> Dict[str, Any]:
    """Submit a task to remove background from an image."""
    url = f"{API_URL}/task"
    
    # Prepare the file for upload
    with open(IMAGE_PATH, "rb") as f:
        file_data = f.read()
    
    # Create form data with the image file
    form_data = aiohttp.FormData()
    form_data.add_field('file', 
                        file_data, 
                        filename='test.jpg', 
                        content_type='image/jpeg')
    
    # Optional request data
    request_data = {
        "custom_data": {
            "request_id": request_id
        }
    }
    form_data.add_field('request_data', json.dumps(request_data))
    
    # Submit the task
    task_start_time = time.time()
    async with session.post(url, data=form_data) as response:
        if response.status != 202:
            print(f"Request {request_id} failed with status {response.status}")
            return {"request_id": request_id, "error": f"HTTP {response.status}"}
        
        result = await response.json()
        task_id = result.get("task_id")
        if not task_id:
            return {"request_id": request_id, "error": "No task_id in response"}
        
        return {
            "request_id": request_id,
            "task_id": task_id,
            "submit_time": task_start_time
        }

async def check_task_status(session: aiohttp.ClientSession, task_info: Dict[str, Any]) -> Dict[str, Any]:
    """Check the status of a task."""
    task_id = task_info["task_id"]
    url = f"{API_URL}/task/{task_id}"
    
    # Poll until the task is completed or failed
    while True:
        async with session.get(url) as response:
            if response.status != 200:
                return {**task_info, "status": "error", "error": f"HTTP {response.status}"}
            
            result = await response.json()
            status = result.get("status")
            
            if status in ["completed", "failed"]:  # Update status check condition to use lowercase values
                end_time = time.time()
                processing_time = end_time - task_info["submit_time"]
                
                return {
                    **task_info,
                    "status": status,
                    "processing_time": processing_time,
                    "result": result
                }
            
            # Wait before polling again
            await asyncio.sleep(0.5)

async def process_request(session: aiohttp.ClientSession, request_id: int) -> Dict[str, Any]:
    """Process a single request from submission to completion."""
    try:
        # Submit the task
        task_info = await submit_task(session, request_id)
        if "error" in task_info:
            return task_info
        
        # Check the task status until completion
        result = await check_task_status(session, task_info)
        return result
    except Exception as e:
        return {"request_id": request_id, "status": "error", "error": str(e)}

async def worker(queue: asyncio.Queue, session: aiohttp.ClientSession) -> None:
    """Worker that processes requests from the queue."""
    while True:
        request_id = await queue.get()
        result = await process_request(session, request_id)
        
        # Store the result
        task_statuses[request_id] = result
        
        # Store processing time for statistics
        if "processing_time" in result:
            status = result.get("status", "unknown")
            processing_times[status].append(result["processing_time"])
        
        # Print progress
        completed = len(task_statuses)
        print(f"Completed {completed}/{TOTAL_REQUESTS} requests. Latest: Request {request_id} - {result.get('status', 'unknown')}")
        
        queue.task_done()

async def main():
    """Main function to run the load test."""
    global start_time, end_time
    
    print(f"Starting load test with {TOTAL_REQUESTS} requests and {CONCURRENCY} concurrent workers")
    print(f"Using image: {IMAGE_PATH}")
    
    # Check if the image file exists
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: Image file {IMAGE_PATH} not found")
        return
    
    # Create a queue to distribute work
    queue = asyncio.Queue()
    
    # Add all requests to the queue
    for i in range(1, TOTAL_REQUESTS + 1):
        queue.put_nowait(i)
    
    # Record the start time
    start_time = time.time()
    
    # Create a session for all HTTP requests
    async with aiohttp.ClientSession() as session:
        # Create workers
        workers = [asyncio.create_task(worker(queue, session)) for _ in range(CONCURRENCY)]
        
        # Wait for all tasks to be processed
        await queue.join()
        
        # Cancel worker tasks
        for w in workers:
            w.cancel()
    
    # Record the end time
    end_time = time.time()
    
    # Print results
    print_results()

def print_results():
    """Print the results of the load test."""
    print("\n" + "="*50)
    print("LOAD TEST RESULTS")
    print("="*50)
    
    # Calculate overall statistics
    total_time = end_time - start_time
    requests_per_second = TOTAL_REQUESTS / total_time
    
    # Count statuses
    status_counts = Counter([result.get("status", "UNKNOWN") for result in task_statuses.values()])
    
    # Print overall statistics
    print(f"\nTotal time: {total_time:.2f} seconds")
    print(f"Requests per second: {requests_per_second:.2f}")
    print(f"Concurrency level: {CONCURRENCY}")
    
    # Print status counts
    print("\nStatus counts:")
    for status, count in status_counts.items():
        print(f"  {status}: {count} ({count/TOTAL_REQUESTS*100:.1f}%)")
    
    # Print processing time statistics
    print("\nProcessing time statistics (seconds):")
    for status, times in processing_times.items():
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            print(f"  {status}:")
            print(f"    Count: {len(times)}")
            print(f"    Avg: {avg_time:.2f}")
            print(f"    Min: {min_time:.2f}")
            print(f"    Max: {max_time:.2f}")
    
    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"load_test_results_{timestamp}.json"
    
    with open(result_file, "w") as f:
        json.dump({
            "config": {
                "total_requests": TOTAL_REQUESTS,
                "concurrency": CONCURRENCY,
                "image_path": IMAGE_PATH,
                "api_url": API_URL
            },
            "overall": {
                "total_time": total_time,
                "requests_per_second": requests_per_second,
                "start_time": start_time,
                "end_time": end_time
            },
            "status_counts": {k: v for k, v in status_counts.items()},
            "task_statuses": {str(k): v for k, v in task_statuses.items()},
            "processing_times": {k: v for k, v in processing_times.items()}
        }, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: {result_file}")

if __name__ == "__main__":
    asyncio.run(main())
