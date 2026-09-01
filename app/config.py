from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Hereshko"
    debug: bool = False
    env: str = "development"

    groq_api_key: str = ""
    groq_whisper_model: str = "whisper-large-v3-turbo"
    groq_llm_model: str = "qwen/qwen3.8-27b"

    gemini_api_key: SecretStr = SecretStr("")
    gemini_embed_model: str = "gemini-embedding-001"

    jina_ai_api_key: str = ""

    tavily_api_key: str = ""
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: str = ""


settings = Settings()
