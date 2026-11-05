import os
import secrets
from typing import List, Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEV_SECRETS = {
    "streetsense_super_secret_jwt_key_for_dev_32char",
    "secret",
    "default",
    "change_me",
    "password",
    "admin",
}


class Settings(BaseSettings):
    PROJECT_NAME: str = "StreetSense Real-Time Sensing & Intelligent Alerting Platform"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./streetsense.db"
    DATABASE_ECHO: bool = False

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # JWT & Identity Security
    JWT_SECRET: str = "streetsense_super_secret_jwt_key_for_dev_32char"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "streetsense:auth"
    JWT_AUDIENCE_DEVICE: str = "streetsense:telemetry"
    JWT_AUDIENCE_CONSOLE: str = "streetsense:console"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24        # 24 hours for devices
    CONSOLE_TOKEN_EXPIRE_MINUTES: int = 60 * 8        # 8 hours for console operator

    # Device Provisioning & Console Authentication
    DEVICE_PROVISIONING_KEY: str = "streetsense_dev_provisioning_master_key_32c"
    CONSOLE_API_KEY: str = "streetsense_dev_console_access_key_32c"

    # WebSocket Ingress Guardrails
    MAX_WS_MESSAGE_SIZE: int = 65536                  # 64 KB strict upper limit
    MAX_TIMESTAMP_SKEW_SECONDS: int = 300             # 5 minutes max clock skew
    WS_RATE_LIMIT_PER_MINUTE: int = 1200              # 20 Hz ceiling per connection
    WS_AUTH_TIMEOUT_SECONDS: float = 5.0              # Handshake timeout window

    # Data Retention & Privacy
    DATA_RETENTION_DAYS: int = 30                     # Purge older raw sensor records

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        is_prod_or_staging = self.ENVIRONMENT in ("production", "staging")

        if is_prod_or_staging:
            if not self.JWT_SECRET or self.JWT_SECRET in INSECURE_DEV_SECRETS or len(self.JWT_SECRET) < 32:
                raise ValueError(
                    f"CRITICAL SECURITY FAILURE: Production and staging require a strong, non-default JWT_SECRET "
                    f"with at least 32 characters. Provided length: {len(self.JWT_SECRET) if self.JWT_SECRET else 0}."
                )
            if not self.DEVICE_PROVISIONING_KEY or self.DEVICE_PROVISIONING_KEY in INSECURE_DEV_SECRETS or len(self.DEVICE_PROVISIONING_KEY) < 32:
                raise ValueError(
                    "CRITICAL SECURITY FAILURE: Production and staging require a secure, non-default DEVICE_PROVISIONING_KEY."
                )
            if not self.CONSOLE_API_KEY or self.CONSOLE_API_KEY in INSECURE_DEV_SECRETS or len(self.CONSOLE_API_KEY) < 32:
                raise ValueError(
                    "CRITICAL SECURITY FAILURE: Production and staging require a secure, non-default CONSOLE_API_KEY."
                )

        # Minimum key length check even in dev/test (RFC 7518)
        if self.JWT_SECRET and len(self.JWT_SECRET.encode("utf-8")) < 32:
            raise ValueError(
                f"JWT_SECRET must be at least 32 bytes (256 bits) for HMAC-SHA256 according to RFC 7518. "
                f"Length was {len(self.JWT_SECRET.encode('utf-8'))} bytes."
            )

        return self


settings = Settings()
