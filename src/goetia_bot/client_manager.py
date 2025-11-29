import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Callable, Dict, Optional

from telethon import TelegramClient, events
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    RPCError,
    AuthRestartError,
)

from .config import Config
from .db import Database, UserRecord

logger = logging.getLogger(__name__)

AgentUsername = "Agent_essence_bot"
MessageCallback = Callable[[int, str, str], Awaitable[None]]  # tg_id, sender, text


class ClientManager:
    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.clients: Dict[int, TelegramClient] = {}
        self._message_callback: Optional[MessageCallback] = None

    def set_message_callback(self, cb: MessageCallback) -> None:
        self._message_callback = cb

    async def start_from_session(self, tg_id: int, session_path: Path) -> Optional[TelegramClient]:
        client = TelegramClient(str(session_path), self.config.api_id, self.config.api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            logger.warning("Сессия для %s не авторизована", tg_id)
            await client.disconnect()
            return None

        self._register_handlers(client, tg_id)
        self.clients[tg_id] = client
        logger.info("Telethon клиент поднят для %s", tg_id)
        return client

    async def start_with_code(self, tg_id: int, phone: str) -> tuple[TelegramClient, Optional[str]]:
        session_path = self._session_path_for(tg_id)
        client = TelegramClient(str(session_path), self.config.api_id, self.config.api_hash)
        await client.connect()
        logger.info("Отправляем код на %s (tg_id=%s)", phone, tg_id)
        last_exc: Optional[Exception] = None
        for attempt in (1, 2):
            try:
                result = await client.send_code_request(phone)
                return client, getattr(result, "phone_code_hash", None)
            except AuthRestartError as e:
                last_exc = e
                logger.warning("AuthRestartError при отправке кода, повтор #%s tg_id=%s", attempt, tg_id)
                await client.disconnect()
                await client.connect()
            except ConnectionError as e:
                last_exc = e
                logger.warning("Проблема соединения при отправке кода, повтор #%s tg_id=%s", attempt, tg_id)
                await client.disconnect()
                await client.connect()
        if last_exc:
            raise last_exc
        raise RuntimeError("Не удалось отправить код")

    async def request_new_code(self, client: TelegramClient, tg_id: int, phone: str, force_sms: bool = False):
        logger.info("Запрос нового кода force_sms=%s для tg_id=%s на %s", force_sms, tg_id, phone)
        result = await client.send_code_request(phone=phone, force_sms=force_sms)
        return getattr(result, "phone_code_hash", None)

    async def finish_sign_in(
        self,
        tg_id: int,
        client: TelegramClient,
        phone: str,
        code: str,
        phone_code_hash: Optional[str] = None,
        password: Optional[str] = None,
    ) -> tuple[bool, bool]:
        password_needed = False
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except (PhoneCodeExpiredError, PhoneCodeInvalidError):
            logger.warning(
                "Код истёк или неверный tg_id=%s phone=%s code_len=%s hash=%s",
                tg_id,
                phone,
                len(code),
                phone_code_hash,
            )
            return False, False
        except SessionPasswordNeededError:
            password_needed = True
            if not password:
                return False, True
            await client.sign_in(password=password)
        except RPCError as e:
            logger.error(
                "RPC ошибка при sign_in tg_id=%s phone=%s code_len=%s: %s",
                tg_id,
                phone,
                len(code),
                e,
            )
            raise

        if not await client.is_user_authorized():
            logger.warning("Не авторизован после sign_in tg_id=%s", tg_id)
            return False, password_needed

        self._register_handlers(client, tg_id)
        self.clients[tg_id] = client
        self.db.set_session_path(tg_id, str(self._session_path_for(tg_id)))
        logger.info("Пользователь %s авторизован, сессия сохранена", tg_id)
        return True, password_needed

    async def complete_with_password(
        self,
        tg_id: int,
        client: TelegramClient,
        password: str,
    ) -> bool:
        await client.sign_in(password=password)
        if not await client.is_user_authorized():
            return False
        self._register_handlers(client, tg_id)
        self.clients[tg_id] = client
        self.db.set_session_path(tg_id, str(self._session_path_for(tg_id)))
        logger.info("Пользователь %s авторизован после 2FA", tg_id)
        return True

    async def stop(self, tg_id: int) -> None:
        client = self.clients.pop(tg_id, None)
        if client:
            await client.disconnect()
            logger.info("Клиент %s остановлен", tg_id)

    def _session_path_for(self, tg_id: int) -> Path:
        self.config.sessions_dir.mkdir(parents=True, exist_ok=True)
        return self.config.sessions_dir / f"user_{tg_id}.session"

    async def send_to_agent(self, tg_id: int, text: str) -> bool:
        client = self.clients.get(tg_id)
        if not client or not await client.is_user_authorized():
            return False
        await client.send_message(AgentUsername, text)
        return True

    def has_client(self, tg_id: int) -> bool:
        return tg_id in self.clients

    def _register_handlers(self, client: TelegramClient, tg_id: int) -> None:
        @client.on(events.NewMessage)
        async def handler(event):  # type: ignore
            if not self._message_callback:
                return

            if event.out:
                return

            user = self.db.get_user(tg_id)
            if not user:
                return

            sender = await event.get_sender()
            username = (getattr(sender, "username", "") or "").lower()
            text = event.message.message or ""

            if username != AgentUsername.lower():
                return

            if not user.passthrough:
                return

            if not text:
                text = "<сообщение без текста или с медиа>"

            await self._message_callback(tg_id, username or "unknown", text)

        # nothing else; handler registration is enough
