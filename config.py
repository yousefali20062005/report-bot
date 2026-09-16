import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


class Config:
    def __init__(self) -> None:
        self.bot_token: str = os.getenv("BOT_TOKEN", "").strip()
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        raw_admins = os.getenv("ADMIN_IDS", "")
        self.admin_ids: list[int] = [
            int(x) for x in raw_admins.split(",") if x.strip().lstrip("-").isdigit()
        ]

    @property
    def ready(self) -> bool:
        return bool(self.bot_token and self.gemini_api_key)