"""Defect classification using YOLO model."""
import io
from functools import lru_cache
from pathlib import Path
import numpy as np

MODEL_PATH = Path("models/civic/civic.pt")


@lru_cache
def _model():
    """Load YOLO model for defect classification."""
    if not MODEL_PATH.exists():
        print(f"Warning: Model not found at {MODEL_PATH}")
        return None
    try:
        from ultralytics import YOLO
        model = YOLO(str(MODEL_PATH))
        print(f"✓ Loaded YOLO model from {MODEL_PATH}")
        return model
    except Exception as e:
        print(f"Error loading YOLO model: {e}")
        return None


def classify_image(image_path: str) -> str:
    """
    Classify defect category from image using YOLO model.
    Returns category string: pothole, streetlight, garbage, drainage, water_supply, road_damage, other
    """
    model = _model()
    
    if model is None:
        # Fallback to simple classification
        print("Warning: YOLO model not available, returning 'other'")
        return "other"
    
    try:
        # Run inference
        results = model(image_path, verbose=False)
        
        if not results or len(results) == 0:
            return "other"
        
        # Get first result
        result = results[0]
        
        # Get class with highest confidence
        if result.boxes and len(result.boxes) > 0:
            # Get the class name of the highest confidence detection
            class_id = int(result.boxes[0].cls[0])
            class_name = result.names[class_id].lower()
            confidence = float(result.boxes[0].conf[0])
            
            # Map YOLO class names to our categories
            category_mapping = {
                'pothole': 'pothole',
                'hole': 'pothole',
                'crack': 'road_damage',
                'streetlight': 'streetlight',
                'light': 'streetlight',
                'lamp': 'streetlight',
                'garbage': 'garbage',
                'trash': 'garbage',
                'waste': 'garbage',
                'litter': 'garbage',
                'drainage': 'drainage',
                'drain': 'drainage',
                'water': 'water_supply',
                'pipe': 'water_supply',
                'leak': 'water_supply',
                'road': 'road_damage',
                'damage': 'road_damage',
                'broken': 'road_damage',
            }
            
            # Check if class name contains any mapping key
            for key, value in category_mapping.items():
                if key in class_name:
                    print(f"✓ YOLO Classification: {value} (detected: {class_name}, confidence: {confidence:.2f})")
                    return value
            
            print(f"✓ YOLO detected: {class_name} (confidence: {confidence:.2f}), defaulting to 'other'")
            return "other"
        
        return "other"
        
    except Exception as e:
        print(f"Error during YOLO classification: {e}")
        return "other"


def get_model_info() -> dict:
    """Get information about the loaded model."""
    model = _model()
    if model is None:
        return {
            "loaded": False,
            "path": str(MODEL_PATH),
            "exists": MODEL_PATH.exists()
        }
    
    return {
        "loaded": True,
        "path": str(MODEL_PATH),
        "exists": True,
        "class_names": list(model.names.values()) if hasattr(model, 'names') else []
    }
