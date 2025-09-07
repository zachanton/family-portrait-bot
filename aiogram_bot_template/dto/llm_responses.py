# aiogram_bot_template/dto/llm_responses.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Any

# 1. Prompt Blueprints


class PromptBlueprint(BaseModel):
    """
    Defines a "job" for the PromptEnhancerService or for direct use.
    It contains either instructions for an enhancer (system_prompt and output_model)
    or a pre-built payload that bypasses the enhancer.
    """
    system_prompt: str | None = None
    output_model: type[BaseModel] | None = None

    enhancer_bypass_payload: dict[str, Any] | None = None

    class Config:
        arbitrary_types_allowed = True


# 2. Pydantic Models for Structured LLM Outputs
#    These models define the exact JSON structure the Enhancer should produce.

class EmptyOutput(BaseModel):
    """An empty Pydantic model for models that take no parameters."""
    model_config = ConfigDict(extra="forbid")


class SinglePromptOutput(BaseModel):
    """Defines a simple JSON object with a single 'prompt' key."""
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(description="The final, complete, and photorealistic prompt for the image generation model.")


class PromptWithNegativeOutput(BaseModel):
    """Defines a JSON object with both 'prompt' and 'negative_prompt' keys."""
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(description="The final, positive prompt for the image generation model.")
    negative_prompt: str = Field(description="A comma-separated list of keywords to avoid.")


class PromptWithControlParams(SinglePromptOutput):
    """Extends the prompt with common control parameters."""
    # This class will inherit the config from its parent, so no change is needed here.
    guidance_scale: float = Field(description="Controls how closely the image generation follows the prompt.")
    num_inference_steps: int = Field(description="The number of denoising steps for the generation.")
