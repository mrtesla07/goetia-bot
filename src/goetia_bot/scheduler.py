import logging
from datetime import time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .client_manager import ClientManager
from .config import Config
from .db import Database, UserRecord

logger = logging.getLogger(__name__)


def parse_time(time_str: str) -> time:
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError("Ожидается формат HH:MM")
    hour = int(parts[0])
    minute = int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Часы/минуты вне диапазона")
    return time(hour=hour, minute=minute)


class BuffScheduler:
    def __init__(self, config: Config, db: Database, clients: ClientManager):
        self.config = config
        self.db = db
        self.clients = clients
        self.scheduler = AsyncIOScheduler(timezone=ZoneInfo(config.timezone))

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Планировщик запущен в TZ %s", self.config.timezone)

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def schedule_user(self, user: UserRecord) -> None:
        self.remove_job(user.tg_id)
        if not user.schedule_enabled:
            return
        try:
            tt = parse_time(user.schedule_time)
        except Exception as e:  # noqa: BLE001
            logger.error("Неверное время %s для %s: %s", user.schedule_time, user.tg_id, e)
            return

        trigger = CronTrigger(hour=tt.hour, minute=tt.minute)
        self.scheduler.add_job(
            self._buff_job,
            trigger=trigger,
            id=str(user.tg_id),
            args=[user.tg_id],
            replace_existing=True,
            misfire_grace_time=3600,
        )
        logger.info("Поставлена авто-/buff для %s на %s", user.tg_id, user.schedule_time)

    def remove_job(self, tg_id: int) -> None:
        job_id = str(tg_id)
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

    async def _buff_job(self, tg_id: int) -> None:
        success = await self.clients.send_to_agent(tg_id, "/buff")
        if success:
            logger.info("Отправлен /buff для %s", tg_id)
        else:
            logger.warning("Не удалось отправить /buff, клиент %s неактивен", tg_id)
