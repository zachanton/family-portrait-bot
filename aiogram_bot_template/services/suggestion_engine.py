# aiogram_bot_template/services/suggestion_engine.py
from typing import Any
from collections.abc import Callable
import structlog

from aiogram_bot_template.dto.facial_features import ImageDescription

logger = structlog.get_logger(__name__)


class SuggestionEngine:
    """
    A class to dynamically generate personalized edit suggestions based on context.
    It acts as a data provider, generating lists of suggestion keys based on a category.
    """

    def __init__(
        self,
        child_desc: ImageDescription | None,
        parent_descs: dict[str, Any] | None,
    ):
        logger.info(
            "SuggestionEngine initialized",
            has_child_desc=child_desc is not None,
            parent_descs_keys=list(parent_descs.keys()) if parent_descs else None
        )

        self.child = child_desc

        self.parents: list[ImageDescription] = []
        if parent_descs:
            for key in ["parent1", "parent2"]:
                if data := parent_descs.get(key):
                    if isinstance(data, dict):
                        self.parents.append(ImageDescription.model_validate(data))
                    elif isinstance(data, ImageDescription):
                        self.parents.append(data)

        self._dynamic_generators: dict[str, Callable[[], list[str]]] = {
            "eyes": self._get_eye_suggestion_keys,
            "skin_details": self._get_skin_suggestion_keys,
            "eyewear": self._get_eyewear_suggestion_keys,
            "jewelry": self._get_jewelry_suggestion_keys,
            "headwear": self._get_headwear_suggestion_keys,
        }

    def generate_dynamic_suggestions(self, dynamic_key: str) -> list[str]:
        """Public method to get dynamic suggestion keys for a specific category key."""
        generator = self._dynamic_generators.get(dynamic_key)
        return generator() if generator else []

    def _get_eye_suggestion_keys(self) -> list[str]:
        """Suggests keys for eye colors from parents that the child doesn't have."""
        if not self.child or not self.child.eyes or not self.child.eyes.color:
            return []

        child_eye_color = self.child.eyes.color.lower()

        parent_eye_colors = set()
        for p in self.parents:
            if p and p.eyes and p.eyes.color:
                parent_eye_colors.add(p.eyes.color.lower())

        logger.info(
            "Eye suggestion check",
            parent_colors=list(parent_eye_colors),
            child_color=child_eye_color,
        )

        color_to_key_map = {
            "green": "eyes_green", "blue": "eyes_blue",
            "brown": "eyes_brown", "hazel": "eyes_hazel",
        }

        generated_keys = []
        for parent_color in parent_eye_colors:
            if parent_color != child_eye_color:
                suggestion_key = color_to_key_map.get(parent_color)
                if suggestion_key:
                    generated_keys.append(suggestion_key)

        logger.info("Generated eye suggestion keys", keys=generated_keys)

        return generated_keys

    def _get_skin_suggestion_keys(self) -> list[str]:
        """Suggests keys for skin details based on context."""
        if not self.child or not self.child.skin: return []

        keys = []
        try:
            parent_has_freckles = any(p.skin.freckles for p in self.parents if p.skin)
            if self.child.skin.freckles:
                keys.append("remove_freckles")
            elif parent_has_freckles:
                keys.append("add_freckles")

            if self.child.skin.dimples:
                keys.append("remove_dimples")
            else:
                keys.append("add_dimples")
        except AttributeError:
            pass

        return keys

    def _get_eyewear_suggestion_keys(self) -> list[str]:
        """Suggests adding or removing glasses based on context."""
        if not self.child: return []
        keys = []
        try:
            if self.child.accessories and self.child.accessories.has_glasses:
                keys.append("remove_glasses")
                keys.append("remove_sunglasses")
            else:
                keys.append("add_glasses")
                keys.append("add_sunglasses")
        except AttributeError:
            keys.append("add_glasses")
            keys.append("add_sunglasses")
        return keys

    def _get_jewelry_suggestion_keys(self) -> list[str]:
        """Suggests adding or removing jewelry based on context."""
        if not self.child: return []
        keys = []
        try:
            if self.child.gender and self.child.gender.lower() == "female":
                if self.child.accessories and self.child.accessories.has_earrings:
                    keys.append("remove_earrings")
                else:
                    keys.append("add_earrings")

            if self.child.accessories and self.child.accessories.has_necklace:
                keys.append("remove_necklace")
            else:
                keys.append("add_necklace")
        except AttributeError:
            if self.child.gender and self.child.gender.lower() == "female":
                keys.append("add_earrings")
            keys.append("add_necklace")
        return keys

    def _get_headwear_suggestion_keys(self) -> list[str]:
        """Suggests adding or removing headwear based on context."""
        if not self.child: return []
        keys = []
        try:
            if self.child.accessories and self.child.accessories.has_hat:
                keys.append("remove_headwear")
            elif self.child.gender and self.child.gender.lower() == "female":
                keys.append("add_tiara")
            elif self.child.gender and self.child.gender.lower() == "male":
                keys.append("add_cap")
        except AttributeError:
            if self.child.gender and self.child.gender.lower() == "female":
                keys.append("add_tiara")
            elif self.child.gender and self.child.gender.lower() == "male":
                keys.append("add_cap")
        return keys
