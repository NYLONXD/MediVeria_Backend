from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Cookie config
    COOKIE_NAME: str = "access_token"
    COOKIE_SECURE: bool = False   # set True in production (requires HTTPS)
    COOKIE_SAMESITE: str = "lax"  # use "none" if frontend/backend are on different domains + COOKIE_SECURE=True
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()