# aiogram_bot_template/services/pipelines/family_photo_pipeline/styles/__init__.py
import importlib
import pkgutil
from typing import Dict, Any

# A dictionary to hold all discovered style modules
STYLES: Dict[str, Dict[str, Any]] = {}

def _register_styles():
    """Dynamically imports and registers all style modules in this package."""
    package_path = __path__
    package_name = __name__

    for _, module_name, _ in pkgutil.iter_modules(package_path):
        # Dynamically import the module
        module = importlib.import_module(f".{module_name}", package_name)

        # Check for required attributes in the module
        style_id = getattr(module, "STYLE_NAME", "").upper().replace(" ", "_")
        style_name_display = getattr(module, "STYLE_NAME", None)
        preview_image_filename = f"{style_id.lower()}.png"

        if style_id and style_name_display:
            STYLES[style_id] = {
                "id": style_id,
                "name": style_name_display,
                "module": module,
                "preview_image": preview_image_filename
            }

# Discover and register styles upon import of this package
_register_styles()