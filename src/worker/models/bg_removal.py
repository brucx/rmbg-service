import os
import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image
import torch
from src.config.logging import model_logger
from src.config import settings

# Global variable to store the singleton model instances (one per worker)
_model_instances = {}

class BackgroundRemovalModel:
    """AI model for removing backgrounds from images."""
    
    @classmethod
    def get_instance(cls, worker_id=None, model_path=None):
        """
        Get or create the singleton model instance for a specific worker.
        
        Args:
            worker_id (int, optional): Worker ID to determine which GPU to use
            model_path (str, optional): Path to the ONNX model file
            
        Returns:
            BackgroundRemovalModel: Singleton model instance for the worker
        """
        global _model_instances
        if worker_id is None:
            worker_id = 0  # Default worker ID
            
        if worker_id not in _model_instances:
            model_logger.info(f"Creating new model instance for worker {worker_id}")
            _model_instances[worker_id] = cls(worker_id=worker_id, model_path=model_path)
        return _model_instances[worker_id]
    
    def __init__(self, worker_id=None, model_path=None):
        """
        Initialize the background removal model.
        
        Args:
            worker_id (int, optional): Worker ID to determine which GPU to use
            model_path (str, optional): Path to the ONNX model file
        """
        self.model_path = model_path or settings.MODEL_PATH
        self.worker_id = worker_id or 0
        
        # Determine which GPU to use based on worker_id
        if settings.DEVICE.lower() == 'cuda' and torch.cuda.is_available():
            # Get total available GPUs
            num_gpus = torch.cuda.device_count()
            if num_gpus > 0:
                # Assign GPU based on worker_id (round-robin)
                self.gpu_id = self.worker_id % num_gpus
                self.device = f"cuda:{self.gpu_id}"
                model_logger.info(f"Worker {self.worker_id} assigned to GPU {self.gpu_id}")
            else:
                self.device = "cpu"
                model_logger.info(f"No GPUs available, using CPU for worker {self.worker_id}")
        else:
            self.device = "cpu"
            model_logger.info(f"Using CPU for worker {self.worker_id}")
            
        self.img_size = settings.IMG_SIZE
        self._load_model()
    
    def _load_model(self):
        """Load the ONNX model for inference."""
        try:
            model_logger.info(f"Loading model from {self.model_path} for worker {self.worker_id}")
            
            # Check if model file exists
            if not os.path.exists(self.model_path):
                model_logger.error(f"Model file not found: {self.model_path}")
                raise FileNotFoundError(f"Model file not found: {self.model_path}")
            
            # Configure ONNX runtime session
            if self.device.startswith('cuda') and torch.cuda.is_available():
                gpu_id = int(self.device.split(':')[1]) if ':' in self.device else 0
                model_logger.info(f"Using CUDA device {gpu_id} for inference")
                # Set environment variable for CUDA device
                os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)
                providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
                provider_options = [{'device_id': gpu_id}, {}]
            else:
                model_logger.info("Using CPU for inference")
                providers = ['CPUExecutionProvider']
                provider_options = [{}]
            
            # Create ONNX runtime session
            self.session = ort.InferenceSession(
                self.model_path, 
                providers=providers,
                provider_options=provider_options
            )
            
            # Get model metadata
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            model_logger.info(f"Model loaded successfully for worker {self.worker_id}")
        except Exception as e:
            model_logger.error(f"Failed to load model for worker {self.worker_id}: {e}")
            raise
    
    def preprocess(self, image_path):
        """
        Preprocess the input image for the model.
        
        Args:
            image_path (str): Path to the input image
            
        Returns:
            np.ndarray: Preprocessed image
        """
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"Failed to read image: {image_path}")
            
            # Convert BGR to RGB
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Save original size for later
            self.orig_h, self.orig_w = img.shape[:2]
            
            # Resize image
            img = cv2.resize(img, (self.img_size, self.img_size))
            
            # Normalize image
            img = img.astype(np.float32) / 255.0
            
            # Transpose from HWC to CHW format
            img = img.transpose(2, 0, 1)
            
            # Add batch dimension
            img = np.expand_dims(img, axis=0)
            
            return img
        except Exception as e:
            model_logger.error(f"Error preprocessing image: {e}")
            raise
    
    def postprocess(self, output, threshold=0.5):
        """
        Postprocess the model output to get the alpha mask.
        
        Args:
            output (np.ndarray): Model output
            threshold (float, optional): Threshold for binary mask
            
        Returns:
            np.ndarray: Alpha mask
        """
        try:
            # Get the mask from output
            mask = output[0][0]
            
            # Resize mask to original image size
            mask = cv2.resize(mask, (self.orig_w, self.orig_h))
            
            # Apply threshold to get binary mask
            mask = (mask > threshold).astype(np.uint8) * 255
            
            return mask
        except Exception as e:
            model_logger.error(f"Error postprocessing output: {e}")
            raise
    
    def remove_background(self, image_path, output_path, alpha_output_path=None, threshold=0.5):
        """
        Remove background from an image and save the result.
        
        Args:
            image_path (str): Path to the input image
            output_path (str): Path to save the output image (RGB)
            alpha_output_path (str, optional): Path to save the alpha mask
            threshold (float, optional): Threshold for binary mask
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            model_logger.info(f"Processing image: {image_path} on {self.device}")
            
            # Preprocess image
            input_tensor = self.preprocess(image_path)
            
            # Run inference
            model_logger.info(f"Running inference on {self.device}")
            outputs = self.session.run([self.output_name], {self.input_name: input_tensor})
            
            # Postprocess output
            mask = self.postprocess(outputs[0], threshold)
            
            # Save alpha mask if requested
            if alpha_output_path:
                cv2.imwrite(alpha_output_path, mask)
                model_logger.info(f"Alpha mask saved to {alpha_output_path}")
            
            # Apply mask to original image
            original_img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
            
            # Check if image has alpha channel, if not add one
            if original_img.shape[2] == 3:
                original_img = cv2.cvtColor(original_img, cv2.COLOR_BGR2BGRA)
            
            # Apply mask to alpha channel
            original_img[:, :, 3] = mask
            
            # Save result
            cv2.imwrite(output_path, original_img)
            model_logger.info(f"Result saved to {output_path}")
            
            return True
        except Exception as e:
            model_logger.error(f"Error removing background: {e}")
            return False
