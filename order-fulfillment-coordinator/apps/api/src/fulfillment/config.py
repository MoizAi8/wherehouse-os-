from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_env_path = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_env_path),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "Order Fulfillment Coordinator"
    app_version: str = "0.1.0"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fulfillment"
    database_sync_url: str = "postgresql://postgres:postgres@localhost:5432/fulfillment"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    cors_origins: list[str] = ["*"]

    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "noreply@fulfillment.com"

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    max_allowed_cost_increase_pct: float = 40.0
    max_notifications_per_order: int = 4
    shipment_poll_interval_seconds: int = 900
    failed_delivery_threshold_pct: float = 10.0
    sla_critical_hours: int = 2


settings = Settings()
