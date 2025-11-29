import os
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def temp_dirs(tmp_path):
    data = tmp_path / "data"
    sessions = tmp_path / "sessions"
    data.mkdir()
    sessions.mkdir()
    return data, sessions


@pytest.fixture(autouse=True)
def clear_env():
    # предотвращаем утечку переменных окружения между тестами
    for key in ("BOT_TOKEN", "API_ID", "API_HASH", "TZ"):
        os.environ.pop(key, None)
    yield
    for key in ("BOT_TOKEN", "API_ID", "API_HASH", "TZ"):
        os.environ.pop(key, None)


# Добавляем src/ в PYTHONPATH для импортов пакета
root = Path(__file__).resolve().parents[1]
src_dir = root / "src"
if src_dir.exists():
    sys.path.insert(0, str(src_dir))
