# aiogram_bot_template/services/enhancers/__init__.py

"""
This package contains services that use a vision-language model (VLM)
to analyze images and generate structured, detailed prompts or hints
for a downstream image generation AI.
"""

from .identity_lock_enhancer import get_identity_lock_data, IdentityLock

__all__ = [
    "get_identity_lock_data",
    "IdentityLock",
]