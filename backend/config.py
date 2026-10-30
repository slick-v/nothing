from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict



# .env is in the project root, one folder above backend/
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    # GROQ
    groq_api_key: str # required: APP wonts start without it 
    model_name: str = "openai/gpt-oss-120b"
    max_tokens: int = 4096
    max_history_messages: int = 20   # how many past messages are sent to the LLM

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")


    # DATABSE
    database_url: str


settings = Settings()
