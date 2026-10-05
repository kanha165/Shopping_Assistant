from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AI Shopping Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database - separate fields (avoids URL special char issues) ───────────
    # All values must be set in .env — no insecure defaults here
    DB_USER: str = "root"
    DB_PASSWORD: str = ""          # set DB_PASSWORD in .env
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "shopping_agent"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # LLM
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_MODEL: str = "gemini-2.5-flash"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    LLM_PROVIDER: str = "google"

    # Security — set a long random SECRET_KEY in .env, never use this default in production
    SECRET_KEY: str = ""           # set SECRET_KEY in .env
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # CORS
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ]

    # RapidAPI key (optional - for Meesho + Myntra)
    # Free key from: https://rapidapi.com
    RAPIDAPI_KEY: Optional[str] = None

    # Playwright
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT: int = 30000

    # Scraper
    MAX_PRODUCTS_PER_PLATFORM: int = 5
    REQUEST_DELAY_MIN: float = 1.0
    REQUEST_DELAY_MAX: float = 3.0

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"    # silently ignore unknown keys in .env (e.g. DATABASE_URL)

    def validate_secrets(self) -> None:
        """Call at startup — raises if required secrets are missing."""
        if not self.DB_PASSWORD:
            raise RuntimeError("DB_PASSWORD must be set in .env")
        if not self.SECRET_KEY:
            raise RuntimeError("SECRET_KEY must be set in .env")


settings = Settings()
