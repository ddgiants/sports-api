from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sports API"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "production"] = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "mysql+asyncmy://sports:sports@127.0.0.1:3307/sports"

    espn_base_url: str = "https://site.web.api.espn.com/apis/site/v2/sports"
    espn_timeout_seconds: float = Field(default=20.0, gt=0)
    espn_max_retries: int = Field(default=3, ge=0, le=10)
    espn_concurrency: int = Field(default=5, ge=1, le=50)
    espn_news_limit: int = Field(default=50, ge=1, le=50)
    espn_team_limit: int = Field(default=1000, ge=1, le=1000)
    espn_user_agent: str = "sports-api/1.0"
    espn_soccer_leagues: str = "eng.1,usa.1"
    espn_include_team_details: bool = True
    espn_strict_sync: bool = False

    cors_origins: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def soccer_league_slugs(self) -> list[str]:
        values = (part.strip() for part in self.espn_soccer_leagues.split(","))
        return list(dict.fromkeys(value for value in values if value))

    @property
    def allowed_origins(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
