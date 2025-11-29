import pytest

from goetia_bot.scheduler import BuffScheduler, parse_time
from goetia_bot.config import Config
from goetia_bot.db import Database, UserRecord


def test_parse_time_ok():
    tt = parse_time("08:15")
    assert tt.hour == 8 and tt.minute == 15


@pytest.mark.parametrize("value", ["24:00", "ab:cd", "9", "09:60", ""])
def test_parse_time_bad(value):
    with pytest.raises(Exception):
        parse_time(value)


def test_schedule_user(monkeypatch, tmp_path):
    cfg = Config(bot_token="t", api_id=1, api_hash="h", timezone="Europe/Moscow")
    db = Database(tmp_path / "db.sqlite3")

    added_jobs = {}

    class DummyScheduler:
        running = False

        def start(self):
            self.running = True

        def shutdown(self, wait=False):
            self.running = False

        def add_job(self, func, trigger, id, args, replace_existing, misfire_grace_time):
            added_jobs[id] = (trigger, args)

        def get_job(self, job_id):
            return added_jobs.get(job_id)

        def remove_job(self, job_id):
            added_jobs.pop(job_id, None)

    dummy = DummyScheduler()
    monkeypatch.setattr("goetia_bot.scheduler.AsyncIOScheduler", lambda timezone=None: dummy)

    class DummyClients:
        async def send_to_agent(self, tg_id, text):
            return True

    scheduler = BuffScheduler(cfg, db, DummyClients())
    scheduler.start()
    user = UserRecord(tg_id=123, schedule_enabled=True, schedule_time="10:00")
    scheduler.schedule_user(user)

    assert "123" in added_jobs
    scheduler.remove_job(123)
    assert "123" not in added_jobs
