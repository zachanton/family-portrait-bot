# aiogram_bot_template/data/constants.py
from enum import Enum


# --- REFACTORED: Added CHILD_GENERATION ---
class GenerationType(str, Enum):
    """Types of generations used in the system."""
    CHILD_GENERATION = "child_generation"
    GROUP_PHOTO = "group_photo"


class ImageRole(str, Enum):
    """Roles for source images."""
    PHOTO_1 = "photo_1"
    PHOTO_2 = "photo_2"

class ChildGender(str, Enum):
    BOY = "boy"
    GIRL = "girl"

class ChildAge(str, Enum):
    INFANT = "2"  # 0-2 years
    CHILD = "7"    # 5-8 years
    TEEN = "14"      # 13-16 years

class ChildResemblance(str, Enum):
    MOM = "mom"
    DAD = "dad"
    BOTH = "both"