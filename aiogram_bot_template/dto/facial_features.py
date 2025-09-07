# aiogram_bot_template/dto/facial_features.py

from pydantic import BaseModel, Field, ConfigDict


class EyeFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: str = Field(description="e.g., 'blue', 'dark brown', 'green'")
    shape: str = Field(description="e.g., 'almond-shaped', 'round', 'hooded'")
    eyelid_type: str = Field(description="e.g., 'monolid', 'double eyelid'")


class HairFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: str = Field(description="e.g., 'blonde', 'jet black', 'auburn'")
    texture: str = Field(description="e.g., 'wavy', 'straight', 'curly', 'coily'")
    length: str = Field(description="e.g., 'short', 'shoulder-length', 'long'")


class FacialStructure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    face_shape: str = Field(description="e.g., 'oval', 'square', 'heart-shaped'")
    nose_shape: str = Field(description="e.g., 'aquiline', 'button', 'straight'")
    lip_shape: str = Field(description="e.g., 'full', 'thin', 'cupid's bow'")
    jawline: str = Field(description="e.g., 'sharp', 'soft', 'square'")
    cheekbones: str = Field(description="e.g., 'high', 'prominent', 'subtle'")
    chin_shape: str = Field(description="e.g., 'pointed', 'square', 'cleft chin'")
    eyebrows_shape: str = Field(description="e.g., 'arched', 'straight', 'thick', 'thin'")


class SkinDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tone: str = Field(description="e.g., 'fair', 'olive', 'tan', 'dark'")
    # REMOVED default=False to make these fields required in the JSON schema
    freckles: bool = Field(description="True if freckles are present on the face")
    dimples: bool = Field(description="True if dimples are visible when smiling")


class AccessoryFeatures(BaseModel):
    """Describes any accessories worn by the person."""
    model_config = ConfigDict(extra="forbid")

    has_glasses: bool = Field(description="True if the person is wearing eyeglasses or sunglasses")
    has_earrings: bool = Field(description="True if earrings are visible")
    has_hat: bool = Field(description="True if the person is wearing a hat, cap, or beanie")

    has_necklace: bool = Field(description="True if a necklace, chain, or choker is visible")


class ImageDescription(BaseModel):
    """A detailed, structured description of a person's facial features."""
    model_config = ConfigDict(extra="forbid")

    gender: str = Field(description="'male' or 'female'")
    ethnicity: str = Field(description="e.g., 'East Asian', 'Black', 'White', 'Latino'")

    eyes: EyeFeatures
    hair: HairFeatures
    facial_structure: FacialStructure
    skin: SkinDetails

    accessories: AccessoryFeatures
