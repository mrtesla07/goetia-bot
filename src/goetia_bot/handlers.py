import asyncio
import logging
from typing import Dict

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from telethon import TelegramClient

from .client_manager import AgentUsername
from .context import AppContext
from .db import UserRecord
from .keyboards import main_menu
from .scheduler import parse_time
from .states import ConnectStates, TimeState

logger = logging.getLogger(__name__)


def setup_router(ctx: AppContext) -> Router:
    router = Router()

    pending_clients: Dict[int, TelegramClient] = {}

    async def render_status(user_id: int) -> str:
        user = ctx.db.get_user(user_id)
        connected = ctx.clients.has_client(user_id)
        lines = [
            "⚙️ Goetia Bot",
            f"Статус подключения: {'✅' if connected else '❌'}",
        ]
        if user:
            lines.append(f"Passthrough: {'ON' if user.passthrough else 'OFF'}")
            lines.append(
                f"Авто /buff: {'ON' if user.schedule_enabled else 'OFF'} {user.schedule_time if user.schedule_enabled else ''}"
            )
        else:
            lines.append("Профиль ещё не создан. Нажмите «Подключить».")
        return "\n".join(lines)

    async def show_menu(message: Message, user: UserRecord | None) -> None:
        connected = ctx.clients.has_client(message.from_user.id)
        kb = main_menu(
            passthrough=user.passthrough if user else False,
            schedule_enabled=user.schedule_enabled if user else False,
        )
        await message.answer(await render_status(message.from_user.id), reply_markup=kb.as_markup())

    @router.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        user = ctx.db.upsert_user(message.from_user.id)
        await show_menu(message, user)

    @router.message(Command("menu"))
    async def cmd_menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        user = ctx.db.upsert_user(message.from_user.id)
        await show_menu(message, user)

    @router.callback_query(F.data == "status")
    async def cb_status(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        await state.clear()
        text = await render_status(callback.from_user.id)
        user = ctx.db.get_user(callback.from_user.id)
        kb = main_menu(user.passthrough if user else False, user.schedule_enabled if user else False)
        await callback.message.edit_text(text, reply_markup=kb.as_markup())

    @router.callback_query(F.data == "connect")
    @router.callback_query(F.data == "reconnect")
    async def cb_connect(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        await state.set_state(ConnectStates.waiting_phone)
        await callback.message.answer("Введите номер телефона (в международном формате, например +79990000000)")

    @router.message(ConnectStates.waiting_phone)
    async def got_phone(message: Message, state: FSMContext) -> None:
        phone = message.text.strip()
        await state.update_data(phone=phone)
        try:
            client = await ctx.clients.start_with_code(message.from_user.id, phone)
            pending_clients[message.from_user.id] = client
        except Exception as e:  # noqa: BLE001
            logger.exception("Ошибка отправки кода: %s", e)
            await message.answer(f"Не удалось отправить код: {e}")
            await state.clear()
            return
        await state.set_state(ConnectStates.waiting_code)
        await message.answer("Код отправлен. Пришлите код из Telegram (6 цифр).")

    @router.message(ConnectStates.waiting_code)
    async def got_code(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        phone = data.get("phone")
        client = pending_clients.get(message.from_user.id)
        if not client or not phone:
            await message.answer("Сессия не найдена, попробуйте заново /start")
            await state.clear()
            return
        code = message.text.strip().replace(" ", "")
        try:
            ok, password_needed = await ctx.clients.finish_sign_in(
                message.from_user.id, client, phone=phone, code=code
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Ошибка авторизации: %s", e)
            await message.answer(f"Не удалось авторизоваться: {e}")
            await state.clear()
            return

        if password_needed and not ok:
            await state.set_state(ConnectStates.waiting_password)
            await message.answer("Включена 2FA. Пришлите пароль от Telegram.")
            return

        if not ok:
            await message.answer("Не удалось авторизоваться, попробуйте заново /start.")
            await state.clear()
            return

        pending_clients.pop(message.from_user.id, None)
        user = ctx.db.upsert_user(message.from_user.id)
        ctx.db.set_passthrough(message.from_user.id, True)
        await state.clear()
        await message.answer("✅ Подключено. Теперь все ваши сообщения пойдут в @Agent_essence_bot.")
        await show_menu(message, user)

    @router.message(ConnectStates.waiting_password)
    async def got_password(message: Message, state: FSMContext) -> None:
        client = pending_clients.get(message.from_user.id)
        if not client:
            await message.answer("Сессия не найдена, начните /start")
            await state.clear()
            return
        password = message.text.strip()
        try:
            ok = await ctx.clients.complete_with_password(message.from_user.id, client, password=password)
        except Exception as e:  # noqa: BLE001
            logger.exception("Ошибка 2FA: %s", e)
            await message.answer(f"Не удалось авторизоваться: {e}")
            await state.clear()
            return
        if not ok:
            await message.answer("Пароль не подошёл. Попробуйте заново /start.")
            await state.clear()
            return
        pending_clients.pop(message.from_user.id, None)
        user = ctx.db.upsert_user(message.from_user.id)
        ctx.db.set_passthrough(message.from_user.id, True)
        await state.clear()
        await message.answer("✅ Подключено с 2FA. Можно пользоваться.")
        await show_menu(message, user)

    @router.callback_query(F.data == "disconnect")
    async def cb_disconnect(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        await state.clear()
        await ctx.clients.stop(callback.from_user.id)
        ctx.db.clear_user(callback.from_user.id)
        session_path = ctx.config.sessions_dir / f"user_{callback.from_user.id}.session"
        if session_path.exists():
            try:
                session_path.unlink()
            except OSError as e:  # noqa: BLE001
                logger.warning("Не смог удалить сессию %s: %s", session_path, e)
        await callback.message.answer("Сессия отключена. Чтобы подключить снова — /start")

    @router.callback_query(F.data == "toggle_passthrough")
    async def cb_passthrough(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        await state.clear()
        user = ctx.db.upsert_user(callback.from_user.id)
        new_state = not user.passthrough
        ctx.db.set_passthrough(callback.from_user.id, new_state)
        await callback.message.answer(
            f"Passthrough теперь {'ON' if new_state else 'OFF'}. "
            f"{'Будут приходить все сообщения.' if new_state else 'Только от @Agent_essence_bot.'}"
        )

    @router.callback_query(F.data == "toggle_schedule")
    async def cb_schedule(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        await state.clear()
        user = ctx.db.upsert_user(callback.from_user.id)
        new_state = not user.schedule_enabled
        ctx.db.set_schedule(callback.from_user.id, new_state)
        user = ctx.db.get_user(callback.from_user.id)
        if user:
            ctx.scheduler.schedule_user(user)
        await callback.message.answer(f"Авто /buff {'включено' if new_state else 'выключено'}.")

    @router.callback_query(F.data == "set_time")
    async def cb_set_time(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        await state.set_state(TimeState.waiting_time)
        await callback.message.answer("Пришлите время в формате HH:MM (по МСК). Пример: 10:30")

    @router.message(TimeState.waiting_time)
    async def got_time(message: Message, state: FSMContext) -> None:
        text = message.text.strip()
        try:
            parse_time(text)
        except Exception as e:  # noqa: BLE001
            await message.answer(f"Неверный формат: {e}")
            return
        ctx.db.set_schedule_time(message.from_user.id, text)
        user = ctx.db.get_user(message.from_user.id)
        if user:
            ctx.scheduler.schedule_user(user)
        await state.clear()
        await message.answer(f"Время для /buff установлено: {text} (МСК)")

    @router.message(F.text)
    async def forward_to_agent(message: Message, state: FSMContext) -> None:
        if await state.get_state():
            return  # в процессе ввода
        if not ctx.clients.has_client(message.from_user.id):
            return
        text = message.text
        sent = await ctx.clients.send_to_agent(message.from_user.id, text)
        if not sent:
            await message.answer("Не удалось отправить, подключение к аккаунту отсутствует.")

    async def on_client_message(tg_id: int, sender: str, text: str) -> None:
        try:
            await ctx.bot.send_message(tg_id, f"[{sender}] {text}")
        except Exception as e:  # noqa: BLE001
            logger.error("Не удалось доставить сообщение %s: %s", tg_id, e)

    ctx.clients.set_message_callback(on_client_message)

    return router
