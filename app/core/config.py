from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EduTrace"
    database_url: str = Field(default="sqlite:///./data/edutrace.db", alias="EDUTRACE_DATABASE_URL")
    upload_dir: Path = Field(default=Path("./uploads"), alias="EDUTRACE_UPLOAD_DIR")
    private_dir: Path = Field(default=Path("./private"), alias="EDUTRACE_PRIVATE_DIR")
    log_level: str = Field(default="INFO", alias="EDUTRACE_LOG_LEVEL")
    privacy_enabled: bool = Field(default=False, alias="EDUTRACE_PRIVACY_ENABLED")
    target_student_query: str = Field(default="", alias="EDUTRACE_TARGET_STUDENT_QUERY")

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.private_dir.mkdir(parents=True, exist_ok=True)
    Path("./data").mkdir(parents=True, exist_ok=True)
    return settings