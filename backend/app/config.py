from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Trader Mini Backend"
    database_url: str = "sqlite:///./backend.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    environment: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
