import os
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from src.config.logging import s3_logger
from src.config import settings

class S3Client:
    """Client for interacting with S3 storage."""
    
    def __init__(self):
        """Initialize S3 client with configuration from settings."""
        self.endpoint = settings.S3_ENDPOINT
        self.access_key = settings.S3_ACCESS_KEY
        self.secret_key = settings.S3_SECRET_KEY
        self.bucket_name = settings.S3_BUCKET_NAME
        self.region = settings.S3_REGION
        self.use_ssl = settings.S3_USE_SSL
        
        # Initialize S3 client
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the S3 client with the provided credentials."""
        # If endpoint is provided, use it (for MinIO, etc.)
        if self.endpoint:
            self.client = boto3.client(
                's3',
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl
            )
        else:
            # Use default AWS S3
            self.client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
        
        # Create bucket if it doesn't exist
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure the specified bucket exists, create it if it doesn't."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            s3_logger.info(f"Bucket {self.bucket_name} exists")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                s3_logger.info(f"Creating bucket {self.bucket_name}")
                try:
                    if self.region == 'us-east-1':
                        self.client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region}
                        )
                except ClientError as ce:
                    s3_logger.error(f"Failed to create bucket: {ce}")
                    raise
            else:
                s3_logger.error(f"Error checking bucket: {e}")
                raise
    
    def upload_file(self, file_path, object_name=None, content_type=None):
        """
        Upload a file to S3 bucket.
        
        Args:
            file_path (str): Path to the file to upload
            object_name (str, optional): S3 object name. If not specified, file_path's basename is used
            content_type (str, optional): Content type of the file
            
        Returns:
            str: URL of the uploaded file
        """
        if not os.path.exists(file_path):
            s3_logger.error(f"File {file_path} does not exist")
            raise FileNotFoundError(f"File {file_path} does not exist")
        
        # If object_name not provided, use file basename
        if object_name is None:
            object_name = os.path.basename(file_path)
        
        # Prepare extra args
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        
        # Upload the file
        try:
            s3_logger.info(f"Uploading {file_path} to {self.bucket_name}/{object_name}")
            self.client.upload_file(
                file_path, 
                self.bucket_name, 
                object_name,
                ExtraArgs=extra_args
            )
            
            # Generate URL for the uploaded file
            url = self._generate_url(object_name)
            s3_logger.info(f"File uploaded successfully: {url}")
            return url
        except ClientError as e:
            s3_logger.error(f"Error uploading file: {e}")
            raise
    
    def _generate_url(self, object_name):
        """Generate a URL for the uploaded object."""
        if self.endpoint:
            # For custom endpoints (MinIO, etc.)
            parsed_url = urlparse(self.endpoint)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            return f"{base_url}/{self.bucket_name}/{object_name}"
        else:
            # For AWS S3
            return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{object_name}"
    
    def download_file(self, object_name, file_path):
        """
        Download a file from S3 bucket.
        
        Args:
            object_name (str): S3 object name
            file_path (str): Path where the file will be saved
            
        Returns:
            bool: True if download was successful, False otherwise
        """
        try:
            s3_logger.info(f"Downloading {self.bucket_name}/{object_name} to {file_path}")
            self.client.download_file(self.bucket_name, object_name, file_path)
            s3_logger.info(f"File downloaded successfully to {file_path}")
            return True
        except ClientError as e:
            s3_logger.error(f"Error downloading file: {e}")
            return False
    
    def delete_file(self, object_name):
        """
        Delete a file from S3 bucket.
        
        Args:
            object_name (str): S3 object name
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            s3_logger.info(f"Deleting {self.bucket_name}/{object_name}")
            self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
            s3_logger.info(f"File deleted successfully")
            return True
        except ClientError as e:
            s3_logger.error(f"Error deleting file: {e}")
            return False
