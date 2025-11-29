import asyncio
from pathlib import Path

import pytest

from goetia_bot.client_manager import ClientManager
from goetia_bot.config import Config
from goetia_bot.db import Database
from telethon.errors import SessionPasswordNeededError


class FakeEvent:
    def __init__(self, text, out=False, username="agent"):
        self.out = out
        self.message = type("msg", (), {"message": text})
        self._username = username

    async def get_sender(self):
        return type("sender", (), {"username": self._username})


class FakeClient:
    def __init__(self, *args, **kwargs):
        self._authorized = False
        self.sent_messages = []
        self.handlers = []
        self.require_password = False
        self.connected = False

    async def connect(self):
        self.connected = True

    async def is_user_authorized(self):
        return self._authorized

    async def send_code_request(self, phone):
        self.phone = phone

    async def sign_in(self, phone=None, code=None, password=None):
        if code and self.require_password:
            raise SessionPasswordNeededError(request=None)
        if password:
            self._authorized = True
        else:
            self._authorized = True

    async def send_message(self, user, text):
        self.sent_messages.append((user, text))

    def on(self, *args, **kwargs):
        def decorator(func):
            self.handlers.append(func)
            return func

        return decorator

    async def disconnect(self):
        self.connected = False


@pytest.fixture()
def manager(tmp_path, monkeypatch, temp_dirs):
    data_dir, sessions_dir = temp_dirs
    cfg = Config(bot_token="t", api_id=1, api_hash="h", data_dir=data_dir, sessions_dir=sessions_dir)
    db = Database(data_dir / "db.sqlite3")
    monkeypatch.setattr("goetia_bot.client_manager.TelegramClient", FakeClient)
    return ClientManager(cfg, db)


@pytest.mark.asyncio
async def test_finish_sign_in(manager: ClientManager):
    client = await manager.start_with_code(tg_id=10, phone="+7000")
    ok, password_needed = await manager.finish_sign_in(tg_id=10, client=client, phone="+7000", code="123456")
    assert ok is True
    assert password_needed is False
    assert manager.has_client(10)
    assert await client.is_user_authorized()


@pytest.mark.asyncio
async def test_finish_sign_in_with_password(manager: ClientManager):
    manager.db.upsert_user(11)
    client = await manager.start_with_code(tg_id=11, phone="+7000")
    client.require_password = True
    ok, password_needed = await manager.finish_sign_in(tg_id=11, client=client, phone="+7000", code="123456")
    assert ok is False and password_needed is True
    ok2 = await manager.complete_with_password(tg_id=11, client=client, password="pwd")
    assert ok2 is True
    assert manager.has_client(11)


@pytest.mark.asyncio
async def test_send_to_agent(manager: ClientManager):
    client = await manager.start_with_code(tg_id=12, phone="+7000")
    await manager.finish_sign_in(tg_id=12, client=client, phone="+7000", code="123456")
    sent = await manager.send_to_agent(12, "ping")
    assert sent is True
    assert ("Agent_essence_bot", "ping") in client.sent_messages


@pytest.mark.asyncio
async def test_handler_passthrough(manager: ClientManager):
    received = []

    async def cb(tg_id, sender, text):
        received.append((tg_id, sender, text))

    manager.set_message_callback(cb)
    manager.db.upsert_user(13)
    client = await manager.start_with_code(tg_id=13, phone="+7000")
    await manager.finish_sign_in(tg_id=13, client=client, phone="+7000", code="123456")
    user = manager.db.get_user(13)
    manager.db.set_passthrough(13, True)
    handler = client.handlers[0]
    await handler(FakeEvent("hello", username="someone"))
    assert received == [(13, "someone", "hello")]
