# aiogram_bot_template/data/constants.py
from enum import Enum


class GenerationType(str, Enum):
    """Types of generations used in the system."""
    GROUP_PHOTO = "group_photo"


class ImageRole(str, Enum):
    """Roles for source images."""
    PHOTO_1 = "photo_1"
    PHOTO_2 = "photo_2"