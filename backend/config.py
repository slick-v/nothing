from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict



# .env is in the project root, one folder above backend/
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    # GROQ
    groq_api_key: str # required: APP wonts start without it 
    model_name: str = "openai/gpt-oss-120b"
    max_tokens: int = 1024

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")


settings = Settings()
