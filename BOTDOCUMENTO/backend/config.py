from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_temperature: float = 0.3
    groq_max_tokens: int = 400
    groq_timeout: int = 60
    cors_origins: Union[str, List[str]] = ["*"]
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    default_font: str = "Arial"
    default_font_size: int = 11
    image_max_width_inches: float = 5.5
    image_download_timeout: int = 10
    max_novedades: int = 5
    auth_enabled: bool = False
    auth_token: str = ""
    auth_exclude_paths: Union[str, List[str]] = ["/api/health"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", "auth_exclude_paths", mode="before")
    def split_strings(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY no está configurada. "
                "Crea un archivo .env basado en .env.example con una API key válida de Groq."
            )

settings = Settings()
