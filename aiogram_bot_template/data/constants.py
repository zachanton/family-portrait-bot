# aiogram_bot_template/data/constants.py
from enum import Enum


class GenerationType(str, Enum):
    """Types of generations used in the system."""

    IMAGE_EDIT = "image_edit"
    CHILD_GENERATION = "child_generation"
    UPSCALE = "upscale"
    GROUP_PHOTO = "group_photo"
    GROUP_PHOTO_EDIT = "group_photo_edit"


class ImageRole(str, Enum):
    """Roles for source images."""

    BASE = "base"
    PARENT_1 = "parent1"
    PARENT_2 = "parent2"
    UPSCALE_SOURCE = "upscale_source"
    GROUP_PHOTO_PARENT_1 = "group_photo_parent_1"
    GROUP_PHOTO_PARENT_2 = "group_photo_parent_2"
    GROUP_PHOTO_CHILD = "group_photo_child"

class SessionContextType(str, Enum):
    """
    Defines the user's current context in a generation session,
    determining which keyboard scenario to display.
    """
    # Scenario A: After a base child generation
    CHILD_GENERATION = "child_generation"
    # Scenario B: After editing a child photo
    EDITED_CHILD = "edited_child"
    # Scenario C: After a group photo generation
    GROUP_PHOTO = "group_photo"
    # Scenario D: After editing a group photo
    EDITED_GROUP_PHOTO = "edited_group_photo"
    # Fallback/Unknown
    UNKNOWN = "unknown"