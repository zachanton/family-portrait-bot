# aiogram_bot_template/data/settings.py

from pydantic import BaseModel, Field, SecretStr, AnyHttpUrl, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseModel):
    token: SecretStr
    admin_id: int | None = None
    log_chat_id: int | None = None
    max_updates_in_queue: int = 100
    support_email: str = "support@example.com"

    @computed_field
    @property
    def id(self) -> int:
        return int(self.token.get_secret_value().split(":")[0])


class DbConfig(BaseModel):
    pg_link: str


class RedisConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 6379
    password: SecretStr | None = None
    username: str | None = None
    fsm_db: int = 1
    cache_db: int = 0


class WebhookConfig(BaseModel):
    address: AnyHttpUrl
    secret_token: SecretStr
    listening_host: str
    listening_port: int


class ProxyConfig(BaseModel):
    base_url: AnyHttpUrl
    listening_host: str
    listening_port: int


class ApiUrls(BaseModel):
    nebius: AnyHttpUrl = "https://api.studio.nebius.ai/v1"
    together: AnyHttpUrl = "https://api.together.xyz/v1"
    openai: AnyHttpUrl = "https://api.openai.com/v1"
    bentoml: AnyHttpUrl = "http://bento-local-ml:3000"
    fal_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None


class QualityTierConfig(BaseModel):
    client: str
    model: str
    price: int
    # Defines the key used for the main image payload. Defaults to 'image_url'.
    # For models expecting a list (like Gemini), this should be 'image_urls'.
    image_payload_key: str = "image_url"


class ImageEditConfig(BaseModel):
    tiers: dict[int, QualityTierConfig]


class GenerationConfig(BaseModel):
    tiers: dict[int, QualityTierConfig]


class UpscaleConfig(BaseModel):
    tiers: dict[int, QualityTierConfig]


class AiFeatureConfig(BaseModel):
    client: str
    model: str
    fallback_model: str | None = None


class CustomApiServerConfig(BaseModel):
    is_local: bool = False
    base: str
    file: str


class FluxConfig(BaseModel):
    model_id: str
    gguf_ckpt_path: str


class QwenConfig(BaseModel):
    model_id: str
    gguf_ckpt_path: str


class GoogleConfig(BaseModel):
    sheet_id: str | None = None
    service_account_creds_json: SecretStr | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    bot: BotConfig
    db: DbConfig
    redis: RedisConfig
    webhook: WebhookConfig
    proxy: ProxyConfig
    api_urls: ApiUrls = Field(default_factory=ApiUrls)

    local_model_provider: str = Field(default="flux", pattern="^(flux|qwen)$")
    flux: FluxConfig | None = None
    qwen: QwenConfig | None = None

    child_generation: GenerationConfig
    image_edit: ImageEditConfig
    upscale: UpscaleConfig
    group_photo: GenerationConfig
    group_photo_edit: ImageEditConfig

    ai_features: dict[str, AiFeatureConfig]

    free_trial_whitelist: list[int] = Field(default_factory=list)

    logging_level: int = 20
    moderation_threshold: float = 0.8
    collect_feedback: bool = False
    google: GoogleConfig | None = None

    use_custom_api_server: bool = False
    custom_api_server: CustomApiServerConfig | None = None


settings = Settings()
