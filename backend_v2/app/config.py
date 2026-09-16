import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///railvision.db")
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "niravaan-secret-key-change-in-production")
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    OR_TOOLS_TIME_LIMIT: int = 30
    EMERGENCY_RADIUS_KM: float = 50.0
    KAVACH_HALT_RADIUS_KM: float = 50.0

    HEALTH_GREEN_THRESHOLD: float = 0.8
    HEALTH_ORANGE_THRESHOLD: float = 0.6
    HEALTH_RED_THRESHOLD: float = 0.4
    HEALTH_DARK_RED_THRESHOLD: float = 0.2

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
