# aiogram_bot_template/services/photo_processing_manager.py
import asyncio
from multiprocessing import Pool
from typing import List, Dict, Tuple, Optional
import numpy as np
import structlog

logger = structlog.get_logger(__name__)

class PhotoProcessingManager:
    """
    An asynchronous manager to offload heavy, CPU-bound photo processing tasks
    to a separate pool of worker processes.
    """
    def __init__(self, pool: Pool):
        """
        Initializes the manager with a pre-configured multiprocessing.Pool.

        Args:
            pool: An instance of multiprocessing.Pool.
        """
        self._pool = pool
        logger.info("PhotoProcessingManager initialized.")

    async def _run_in_worker(self, func, *args):
        """
        A helper to run a function in the worker pool and await its result
        without blocking the event loop.
        """
        loop = asyncio.get_running_loop()
        # Use run_in_executor to run the blocking get() call in a separate thread
        return await loop.run_in_executor(
            None, lambda: self._pool.apply(func, args=args)
        )

    async def process_photo_batch(
        self, photo_inputs: List[Tuple[bytes, str, str]]
    ) -> Optional[List[Tuple[str, str, bytes]]]:
        """
        Offloads the analysis and processing of a batch of photos to a worker process.

        Args:
            photo_inputs: A list of tuples containing (photo_bytes, unique_id, file_id).

        Returns:
            A list of tuples with (unique_id, file_id, processed_photo_bytes) for valid photos,
            or None if processing fails or no photos are suitable.
        """
        logger.info("Offloading photo batch processing to worker.", count=len(photo_inputs))
        # Dynamically import the worker function to avoid circular dependencies at module level
        from . import photo_processor_service
        return await self._run_in_worker(
            photo_processor_service.process_photo_batch_worker,
            photo_inputs
        )

    async def calculate_identity_centroid(
        self, image_bytes_list: List[bytes]
    ) -> Optional[np.ndarray]:
        """
        Offloads the calculation of an identity centroid to a worker process.

        Args:
            image_bytes_list: A list of byte strings for the images.

        Returns:
            A numpy array for the centroid, or None.
        """
        logger.info("Offloading identity centroid calculation to worker.", count=len(image_bytes_list))
        from . import photo_processor_service
        return await self._run_in_worker(
            photo_processor_service.calculate_identity_centroid_worker,
            image_bytes_list
        )
        
    async def sort_and_filter_by_identity(
        self, photos_data: List[Dict], target_count: int
    ) -> List[Dict]:
        """
        Offloads identity-based sorting and filtering to a worker process.

        Args:
            photos_data: List of dicts, each with a 'bytes' key.
            target_count: The desired number of photos.

        Returns:
            A sorted and filtered list of photo dicts.
        """
        logger.info("Offloading identity sorting/filtering to worker.", count=len(photos_data))
        from . import photo_processor_service
        return await self._run_in_worker(
            photo_processor_service.sort_and_filter_by_identity_worker,
            photos_data,
            target_count
        )

    async def extract_face_features(self, image_bytes: bytes) -> Optional[dict]:
        """
        Offloads face feature extraction for a single image to a worker process.

        Args:
            image_bytes: The byte string of the image.

        Returns:
            A dictionary containing the face features, or None.
        """
        from . import photo_processor_service
        return await self._run_in_worker(
            photo_processor_service.extract_face_features_worker,
            image_bytes
        )

    async def create_portrait_collage(self, tiles_bytes: List[bytes]) -> Optional[bytes]:
        """
        Offloads the creation of a 2x2 collage to a worker process.

        Args:
            tiles_bytes: A list of 4 byte strings for the pre-processed tiles.

        Returns:
            The final collage image as JPEG bytes, or None.
        """
        logger.info("Offloading collage creation to worker.")
        from . import photo_processor_service
        return await self._run_in_worker(
            photo_processor_service.create_portrait_collage_worker,
            tiles_bytes
        )

    async def split_and_stack_image(self, image_bytes: bytes) -> tuple[bytes | None, bytes | None]:
        """
        Offloads splitting a composite image to a worker process.

        Args:
            image_bytes: The byte string of the composite image.

        Returns:
            A tuple containing the bytes of the front and side views.
        """
        from . import photo_processor_service
        return await self._run_in_worker(
            photo_processor_service.split_and_stack_image_worker,
            image_bytes
        )

    async def stack_images_horizontally(self, img_left_bytes: bytes, img_right_bytes: bytes) -> Optional[bytes]:
        """
        Offloads horizontal image stacking to a worker process.
        """
        from . import photo_processor_service
        return await self._run_in_worker(
            photo_processor_service.stack_images_horizontally_worker,
            img_left_bytes, img_right_bytes
        )

    async def stack_two_images(self, img_top_bytes: bytes, img_bottom_bytes: bytes) -> Optional[bytes]:
        """
        Offloads vertical image stacking to a worker process.
        """
        from . import photo_processor_service
        return await self._run_in_worker(
            photo_processor_service.stack_two_images_worker,
            img_top_bytes, img_bottom_bytes
        )