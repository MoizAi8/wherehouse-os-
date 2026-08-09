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

    app_name: str = "FulfillOS"
    app_version: str = "0.1.0"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fulfillment"
    database_sync_url: str = "postgresql://postgres:postgres@localhost:5432/fulfillment"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    jwt_refresh_expiration_days: int = 7
    jwt_password_reset_expiration_minutes: int = 30

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    rate_limit_enabled: bool = True
    rate_limit_default: str = "120/minute"
    rate_limit_auth: str = "10/minute"
    rate_limit_chat: str = "30/minute"

    webhook_secret: str = "change-webhook-secret"

    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "noreply@fulfillment.com"

    reset_email_redirect_url: str = "http://localhost:3000/reset-password"

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    max_allowed_cost_increase_pct: float = 40.0
    max_notifications_per_order: int = 4
    shipment_poll_interval_seconds: int = 900
    failed_delivery_threshold_pct: float = 10.0
    sla_critical_hours: int = 2

    odoo_url: str = ""
    odoo_db: str = ""
    odoo_username: str = ""
    odoo_password: str = ""
    odoo_verify_ssl: bool = True

    integration_secret_key: str = ""


settings = Settings()
