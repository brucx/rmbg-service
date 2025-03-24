import json
import requests
from requests.exceptions import RequestException
from src.config.logging import callback_logger
from src.config import settings

class CallbackClient:
    """Client for sending callbacks to external services."""
    
    def __init__(self):
        """Initialize callback client with configuration from settings."""
        self.enabled = settings.CALLBACK_ENABLED
        self.callback_url = settings.CALLBACK_URL
        self.auth_token = settings.CALLBACK_AUTH_TOKEN
    
    def send_callback(self, task_id, status, result_url=None, error=None):
        """
        Send a callback notification to the configured URL.
        
        Args:
            task_id (str): ID of the task
            status (str): Status of the task (pending, processing, completed, failed)
            result_url (str, optional): URL of the result file
            error (str, optional): Error message if task failed
            
        Returns:
            bool: True if callback was sent successfully, False otherwise
        """
        if not self.enabled or not self.callback_url:
            callback_logger.info(f"Callbacks disabled or URL not configured. Task {task_id} status: {status}")
            return False
        
        # Prepare callback data
        callback_data = {
            "task_id": task_id,
            "status": status,
        }
        
        if result_url:
            callback_data["result_url"] = result_url
        
        if error:
            callback_data["error"] = error
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json"
        }
        
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        # Send callback
        try:
            callback_logger.info(f"Sending callback for task {task_id}, status: {status}")
            response = requests.post(
                self.callback_url,
                json=callback_data,
                headers=headers,
                timeout=10
            )
            
            if response.ok:
                callback_logger.info(f"Callback sent successfully for task {task_id}")
                return True
            else:
                callback_logger.error(
                    f"Failed to send callback for task {task_id}. "
                    f"Status code: {response.status_code}, Response: {response.text}"
                )
                return False
        except RequestException as e:
            callback_logger.error(f"Exception sending callback for task {task_id}: {e}")
            return False
