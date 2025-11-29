import os

import pytest

from goetia_bot.config import load_config


def test_load_config_ok(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "BOT_TOKEN=test\nAPI_ID=12345\nAPI_HASH=hash\nTZ=Europe/Moscow\n", encoding="utf-8"
    )
    cfg = load_config(str(env_path))
    assert cfg.bot_token == "test"
    assert cfg.api_id == 12345
    assert cfg.api_hash == "hash"
    assert cfg.timezone == "Europe/Moscow"


def test_load_config_missing_token(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("API_ID=1\nAPI_HASH=h\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_config(str(env_path))


def test_load_config_missing_api(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("BOT_TOKEN=test\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_config(str(env_path))
