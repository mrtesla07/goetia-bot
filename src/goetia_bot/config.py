import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    bot_token: str
    api_id: int
    api_hash: str
    timezone: str = "Europe/Moscow"
    data_dir: Path = Path("data")
    sessions_dir: Path = Path("sessions")


def load_config(env_file: str = ".env") -> Config:
    load_dotenv(env_file)

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    api_id = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    timezone = os.getenv("TZ", "Europe/Moscow").strip() or "Europe/Moscow"

    if not bot_token:
        raise RuntimeError("Не указан BOT_TOKEN в .env")
    if not api_id or not api_hash:
        raise RuntimeError("Не заданы API_ID / API_HASH (my.telegram.org/apps)")

    return Config(
        bot_token=bot_token,
        api_id=int(api_id),
        api_hash=api_hash,
        timezone=timezone,
        data_dir=Path("data"),
        sessions_dir=Path("sessions"),
    )
