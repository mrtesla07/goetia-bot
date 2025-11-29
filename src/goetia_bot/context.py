from dataclasses import dataclass

from aiogram import Bot

from .client_manager import ClientManager
from .config import Config
from .db import Database
from .scheduler import BuffScheduler


@dataclass
class AppContext:
    config: Config
    db: Database
    clients: ClientManager
    scheduler: BuffScheduler
    bot: Bot
