# aiogram_bot_template/data/constants.py
from enum import Enum


class GenerationType(str, Enum):
    """Types of generations used in the system."""
    CHILD_GENERATION = "child_generation"
    PAIR_PHOTO = "pair_photo"  # Renamed from GROUP_PHOTO
    FAMILY_PHOTO = "family_photo"  # New type for 3 people


class ImageRole(str, Enum):
    """Roles for source images."""
    FATHER = "father"
    MOTHER = "mother"
    CHILD = "child"


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