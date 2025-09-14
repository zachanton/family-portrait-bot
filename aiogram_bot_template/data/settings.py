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
    # --- OpenRouter Settings ---
    openrouter: AnyHttpUrl = "https://openrouter.ai/api/v1"
    openrouter_api_key: SecretStr | None = None


class QualityTierConfig(BaseModel):
    client: str
    model: str
    price: int
    count: int = 1
    image_payload_key: str = "image_urls"


class GenerationConfig(BaseModel):
    tiers: dict[int, QualityTierConfig]


class GoogleConfig(BaseModel):
    sheet_id: str | None = None
    service_account_creds_json: SecretStr | None = None

class PromptEnhancerConfig(BaseModel):
    """Configuration for the prompt enhancement service."""
    enabled: bool = True
    client: str = "openai"
    model: str = "gpt-4o-mini"


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

    group_photo: GenerationConfig

    prompt_enhancer: PromptEnhancerConfig = Field(default_factory=PromptEnhancerConfig)

    free_trial_whitelist: list[int] = Field(default_factory=list)

    logging_level: int = 20
    collect_feedback: bool = True
    google: GoogleConfig | None = None


settings = Settings()