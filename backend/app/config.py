from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str | None = None
    vision_model: str = "gpt-5.1"
    embedding_model: str = "text-embedding-3-small"
    database_url: str = "postgresql://partiq:partiq@localhost:5432/partiq"
    upload_dir: Path = Path("storage/uploads")
    crop_dir: Path = Path("storage/crops")
    cost_currency: str = "INR"
    usd_to_inr_rate: float = 83.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
