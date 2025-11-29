import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .client_manager import ClientManager
from .config import load_config
from .context import AppContext
from .db import Database
from .handlers import setup_router
from .scheduler import BuffScheduler


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def create_app() -> tuple[Dispatcher, AppContext]:
    setup_logging()
    config = load_config()

    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.sessions_dir.mkdir(parents=True, exist_ok=True)

    db = Database(config.data_dir / "goetia.db")
    bot = Bot(token=config.bot_token, parse_mode="HTML")
    clients = ClientManager(config, db)
    scheduler = BuffScheduler(config, db, clients)
    ctx = AppContext(config=config, db=db, clients=clients, scheduler=scheduler, bot=bot)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(setup_router(ctx))

    await restore_clients(ctx)
    scheduler.start()

    return dp, ctx


async def restore_clients(ctx: AppContext) -> None:
    users = ctx.db.list_users().values()
    for user in users:
        if user.session_path and Path(user.session_path).exists():
            try:
                await ctx.clients.start_from_session(user.tg_id, Path(user.session_path))
            except Exception as e:  # noqa: BLE001
                logging.getLogger(__name__).warning("Не удалось поднять сессию %s: %s", user.tg_id, e)
        if user.schedule_enabled:
            ctx.scheduler.schedule_user(user)


async def run() -> None:
    dp, ctx = await create_app()
    try:
        await dp.start_polling(ctx.bot)
    finally:
        await ctx.bot.session.close()
        ctx.scheduler.shutdown()
        for tg_id in list(ctx.clients.clients.keys()):
            await ctx.clients.stop(tg_id)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
