from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    llm_api_keys: str = ''
    llm_model: str = 'gemini/gemini-2.5-flash-lite'
    database_url: str = 'sqlite:///./app.db'
    allowed_origins: str = 'http://localhost:3000'
    enable_failure_simulation: bool = False
    default_system_prompt: str = 'You are a helpful, concise assistant.'
    cache_ttl_seconds: int = 3600

    @property
    def keys(self) -> list[str]:
        return [key.strip() for key in self.llm_api_keys.split(',') if key.strip()]

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(',') if origin.strip()]

settings = Settings()
