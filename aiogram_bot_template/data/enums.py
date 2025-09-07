from enum import Enum


class AiFeature(str, Enum):
    """Enumeration of non-generating AI features used in the application."""

    VISION_ANALYSIS = "vision_analysis"
    PROMPT_ENHANCER = "prompt_enhancer"
