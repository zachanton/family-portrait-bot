# aiogram_bot_template/services/photo_processor_service.py
from typing import List, Optional, Tuple, Dict
import numpy as np

# Important: All heavy imports like insightface, cv2, etc.,
# should be inside the functions or guarded to be used only by worker processes.
from aiogram_bot_template.services import similarity_scorer, photo_processing

# --- Worker Initializer ---
def initialize_worker():
    """
    Initializes resource-heavy models within each worker process.
    This is crucial to avoid pickling large objects from the main process
    and ensures each worker has its own instance of the model in memory.
    """
    print(f"Initializing models for worker process...")
    similarity_scorer._get_face_analysis_app()
    photo_processing._get_face_analysis_app()
    print(f"Worker process initialized successfully.")


# --- Worker Task Functions ---

def process_photo_batch_worker(
    photo_inputs: List[Tuple[bytes, str, str]]
) -> Optional[List[Tuple[str, str, bytes]]]:
    """
    This function runs in a separate process.
    It takes raw photo bytes, performs all heavy CPU-bound analysis,
    and returns a list of processed photos that are ready for caching.
    
    Args:
        photo_inputs: A list of tuples, each containing (photo_bytes, unique_id, file_id).

    Returns:
        A list of tuples with (unique_id, file_id, processed_photo_bytes) for valid photos,
        or None if no photos were suitable.
    """
    return similarity_scorer.select_best_photos_and_process_sync(photo_inputs)

def calculate_identity_centroid_worker(
    image_bytes_list: List[bytes]
) -> Optional[np.ndarray]:
    """
    This function runs in a separate process to calculate the identity centroid
    from a list of image bytes.

    Args:
        image_bytes_list: A list of byte strings for the images.

    Returns:
        A numpy array representing the identity centroid, or None.
    """
    return similarity_scorer.calculate_identity_centroid_sync(image_bytes_list)

def sort_and_filter_by_identity_worker(
    photos_data: List[Dict], target_count: int
) -> List[Dict]:
    """
    This function runs in a separate process to perform identity-based filtering
    and sorting.

    Args:
        photos_data: A list of dictionaries, each with at least a 'bytes' key.
        target_count: The desired number of photos in the output list.

    Returns:
        A list of 'target_count' photos, sorted by identity similarity.
    """
    return similarity_scorer.sort_and_filter_by_identity_sync(photos_data, target_count)

# --- NEW WORKER FUNCTIONS ---

def extract_face_features_worker(image_bytes: bytes) -> Optional[dict]:
    """
    Worker function to extract face features from a single image's bytes.
    Designed to run in a separate process.
    """
    return similarity_scorer._extract_face_features_sync(image_bytes)

def create_portrait_collage_worker(tiles_bytes: List[bytes]) -> Optional[bytes]:
    """
    Worker function to create a 2x2 collage from processed tiles.
    Designed to run in a separate process.
    """
    return photo_processing.create_portrait_collage_from_bytes(tiles_bytes)

def split_and_stack_image_worker(image_bytes: bytes) -> tuple[bytes | None, bytes | None]:
    """
    Worker function to split a composite image into its front and side views.
    Designed to run in a separate process.
    """
    return photo_processing.split_and_stack_image_bytes(image_bytes)

def stack_images_horizontally_worker(img_left_bytes: bytes, img_right_bytes: bytes) -> Optional[bytes]:
    """
    Worker function to stack two images horizontally.
    Designed to run in a separate process.
    """
    return photo_processing.stack_images_horizontally(img_left_bytes, img_right_bytes)

def stack_two_images_worker(img_top_bytes: bytes, img_bottom_bytes: bytes) -> Optional[bytes]:
    """
    Worker function to stack two images vertically.
    Designed to run in a separate process.
    """
    return photo_processing.stack_two_images(img_top_bytes, img_bottom_bytes)