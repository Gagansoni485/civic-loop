"""Privacy protection: Face detection and blurring, metadata stripping."""
import os
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS


def detect_faces(image_path: str) -> list:
    """Detect faces in an image using OpenCV."""
    # Load the cascade classifier
    face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(face_cascade_path)
    
    # Read image
    img = cv2.imread(image_path)
    if img is None:
        return []
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Detect faces
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30)
    )
    
    return faces.tolist() if len(faces) > 0 else []


def blur_faces(image_path: str, output_path: str, blur_strength: int = 51) -> Tuple[bool, int]:
    """Blur detected faces in an image.
    
    Returns:
        (success, face_count)
    """
    faces = detect_faces(image_path)
    
    if not faces:
        # No faces detected, just copy the image
        img = cv2.imread(image_path)
        cv2.imwrite(output_path, img)
        return True, 0
    
    # Read image
    img = cv2.imread(image_path)
    
    # Blur each detected face
    for (x, y, w, h) in faces:
        # Extract face region
        face = img[y:y+h, x:x+w]
        
        # Apply Gaussian blur
        blurred_face = cv2.GaussianBlur(face, (blur_strength, blur_strength), 30)
        
        # Replace face region with blurred version
        img[y:y+h, x:x+w] = blurred_face
    
    # Save blurred image
    cv2.imwrite(output_path, img)
    
    return True, len(faces)


def strip_metadata(image_path: str, output_path: str) -> bool:
    """Remove all EXIF metadata from an image.
    
    This removes GPS coordinates, camera info, timestamps, etc.
    """
    try:
        # Open image
        img = Image.open(image_path)
        
        # Create a new image without EXIF data
        # Convert to RGB if necessary (handle RGBA, P modes)
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        
        # Save without EXIF
        img.save(output_path, quality=95, optimize=True)
        
        return True
    except Exception as e:
        print(f"Error stripping metadata: {e}")
        return False


def process_image_for_privacy(
    input_path: str,
    output_dir: str,
    blur_faces_enabled: bool = True
) -> Tuple[str, dict]:
    """Process an image for privacy: blur faces and strip metadata.
    
    Args:
        input_path: Path to input image
        output_dir: Directory to save processed image
        blur_faces_enabled: Whether to blur faces
    
    Returns:
        (output_path, metadata) where metadata contains:
        - contains_faces: bool
        - face_count: int
        - metadata_stripped: bool
        - original_size: tuple
        - processed_size: tuple
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate output filename
    input_filename = Path(input_path).name
    base_name = Path(input_path).stem
    extension = Path(input_path).suffix
    temp_path = os.path.join(output_dir, f"{base_name}_temp{extension}")
    output_path = os.path.join(output_dir, input_filename)
    
    metadata = {
        "contains_faces": False,
        "face_count": 0,
        "metadata_stripped": False,
        "original_size": 0,
        "processed_size": 0
    }
    
    # Get original file size
    metadata["original_size"] = os.path.getsize(input_path)
    
    # Step 1: Blur faces if enabled
    if blur_faces_enabled:
        success, face_count = blur_faces(input_path, temp_path)
        if success:
            metadata["contains_faces"] = face_count > 0
            metadata["face_count"] = face_count
        current_path = temp_path
    else:
        current_path = input_path
    
    # Step 2: Strip metadata
    success = strip_metadata(current_path, output_path)
    metadata["metadata_stripped"] = success
    
    # Get processed file size
    metadata["processed_size"] = os.path.getsize(output_path)
    
    # Clean up temp file
    if blur_faces_enabled and os.path.exists(temp_path):
        os.remove(temp_path)
    
    return output_path, metadata


def check_image_privacy(image_path: str) -> dict:
    """Check privacy status of an image without modifying it.
    
    Returns:
        - has_faces: bool
        - face_count: int
        - has_metadata: bool
        - metadata_keys: list
    """
    result = {
        "has_faces": False,
        "face_count": 0,
        "has_metadata": False,
        "metadata_keys": []
    }
    
    # Check for faces
    faces = detect_faces(image_path)
    result["has_faces"] = len(faces) > 0
    result["face_count"] = len(faces)
    
    # Check for metadata
    try:
        img = Image.open(image_path)
        exif = img.getexif()
        if exif:
            result["has_metadata"] = True
            result["metadata_keys"] = [
                TAGS.get(tag, tag) for tag in exif.keys()
            ]
    except Exception:
        pass
    
    return result
