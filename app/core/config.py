from typing import ClassVar
from pydantic_settings import BaseSettings
from fastapi.security import OAuth2PasswordBearer


class Settings(BaseSettings):
    base_url: str

    # Render / Prod: set DATABASE_URL in Render dashboard
    database_url: str

    # For OAuth / JWT later
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    app_deep_link: str
    oauth2_scheme: ClassVar[OAuth2PasswordBearer] = OAuth2PasswordBearer(tokenUrl="token")
    openai_api_key: str

    class Config:
        env_file = ".env.template"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()