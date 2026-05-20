from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://mint_user:mint_pass@localhost:5432/mint_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "dev-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    ENVIRONMENT: str = "development"
    BACKEND_CORS_ORIGINS: str = '["http://localhost:5173","http://localhost:3000"]'
    OPENAI_API_KEY: str = ""
    OTEL_ENDPOINT: str = "http://jaeger:4317"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    LOCAL_RECEIPTS_DIR: str = "/tmp/mint_receipts"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    def get_cors_origins(self) -> List[str]:
        if not self.BACKEND_CORS_ORIGINS:
            return []
        return json.loads(self.BACKEND_CORS_ORIGINS)

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
