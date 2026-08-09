from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Trader Mini Backend"
    database_url: str = "sqlite:///./backend.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    environment: str = "development"
    telegram_bot_token: str = ""
    telegram_webapp_url: str = ""
    telegram_funnel_enabled: bool = False
    telegram_funnel_allowed_user_ids: str = ""
    telegram_source_channel_id: str = ""
    team_vip_url: str = ""
    pocket_option_partner_id: str = ""
    pocket_option_api_token: str = ""
    pocket_option_api_base_url: str = "https://affiliate.pocketoption.com/api"
    pocket_option_ref_ru_url: str = ""
    pocket_option_ref_ww_url: str = ""
    devsbite_client_token: str = ""
    devsbite_api_base_url: str = "https://api.devsbite.com"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url

    @property
    def telegram_funnel_allowed_user_id_set(self) -> set[int]:
        allowed_ids: set[int] = set()
        for raw_id in self.telegram_funnel_allowed_user_ids.split(","):
            value = raw_id.strip()
            if value.isdigit():
                allowed_ids.add(int(value))
        return allowed_ids

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
