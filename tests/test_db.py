from goetia_bot.db import Database


def test_db_crud(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    user = db.upsert_user(100)
    assert user.tg_id == 100
    assert user.passthrough is False
    assert user.schedule_enabled is False

    db.set_passthrough(100, True)
    db.set_schedule(100, True, "09:30")
    db.set_session_path(100, "sessions/user_100.session")

    user2 = db.get_user(100)
    assert user2.passthrough is True
    assert user2.schedule_enabled is True
    assert user2.schedule_time == "09:30"
    assert user2.session_path == "sessions/user_100.session"

    db.clear_user(100)
    user3 = db.get_user(100)
    assert user3.passthrough is False
    assert user3.schedule_enabled is False
    assert user3.session_path is None
