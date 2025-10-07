from pydantic import AnyUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Render / Prod: set DATABASE_URL in Render dashboard
    database_url: str

    # For OAuth / JWT later
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    app_deep_link: str = "dosemate://auth/callback"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()