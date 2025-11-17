from __future__ import annotations

"""Central application settings loaded from environment and .env files."""

from pathlib import Path

from pydantic import BaseModel, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Compute likely .env locations: repository root and src/.env
_HERE = Path(__file__).parent.resolve()
_SRC_DIR = _HERE.parent
_ROOT_DIR = _SRC_DIR.parent
_ENV_FILE = _ROOT_DIR / ".env"


class LoggerConfig(BaseSettings):
    # Support LOG_LEVEL, LOG_NAME by prefix
    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        extra="ignore",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        frozen=True,
    )
    level: str = Field(default="INFO", min_length=1)
    name: str = Field(default="email-agent", min_length=1)


class PineconeConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PINECONE_",
        extra="ignore",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        frozen=True,
    )
    api_key: str = Field(default="", min_length=1, exclude=True, repr=False)
    namespace: str = Field(default="", min_length=1)
    index: str = Field(default="", min_length=1)


class AppConfig(BaseSettings):
    """Application-level configuration loaded from .env.

    APP_WATCH_FOLDER_PATH specifies the target mail folder path to monitor, e.g.:
    "inbox/AI-Assistant"
    Path is case-insensitive for well-known folder name (e.g., inbox) and folder display names.
    Segments are separated by "/".
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        extra="ignore",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        frozen=True,
    )

    watch_folder_path: str = Field(
        default="inbox",
        description="Mail folder path to watch (e.g., 'inbox/AI-Assistant')",
        min_length=1,
    )

    watch_user: str = Field(
        default="",
        description="Primary mailbox user principal name (email) to monitor",
        min_length=1,
    )

    poll_interval_seconds: int = Field(
        default=30,
        ge=5,
        description="How often to poll the watch folder for new messages (in seconds)",
    )

    processing_category_prefix: str = Field(
        default="CERM-AI",
        description="Category name prefix applied to messages while being processed",
        min_length=1,
    )

    allow_mail_domains: str = Field(
        default="*",
        description="Comma-separated list of allowed sender domains (e.g. '@example.com, @example.org') or '*' for all",
        min_length=1,
    )

    class ProcessingCategoryConfig(BaseModel):
        prefix: str

        @property
        def processing(self) -> str:  # Message is currently being processed
            return f"{self.prefix}:Processing"

        @property
        def success(self) -> str:  # Processing completed successfully
            return f"{self.prefix}:Success"

        @property
        def failed(self) -> str:  # Processing failed
            return f"{self.prefix}:Failed"

    @computed_field
    def processing_category(self) -> ProcessingCategoryConfig:
        """Derived category labels based on configured prefix.

        Uses the resolved value of processing_category_prefix after environment
        variables and .env overrides have been loaded (instead of capturing the
        Field definition object at class definition time).
        """
        return self.ProcessingCategoryConfig(prefix=self.processing_category_prefix)

    @computed_field
    def allow_mail_domain_list(self) -> str | list[str]:
        """Normalized list of allowed sender domains.

        Returns ['*'] when all domains are allowed. Whitespace is stripped and
        domains are lower-cased. Ensures each entry starts with '@' if not '*'.
        """
        raw = (self.allow_mail_domains or "*").strip()
        if raw == "*":
            return "*"
        parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
        normalized: list[str] = []
        for p in parts:
            if p == "*":
                return "*"  # wildcard overrides others
            if not p.startswith("@"):
                p = f"@{p}"
            normalized.append(p)
        return normalized or "*"


class Settings(BaseSettings):
    # Let pydantic-settings load .env files directly
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pinecone: PineconeConfig = PineconeConfig()
    app: AppConfig = AppConfig()


settings = Settings()

if _ENV_FILE:
    print(f"Loaded env from: {_ENV_FILE}")
else:
    print("No .env file found; relying on process environment only")

if __name__ == "__main__":
    from rich import print

    print(settings)

    print("API keys & secrets are not printed. Double check if they are present!")
