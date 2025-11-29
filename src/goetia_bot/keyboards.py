from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu(passthrough: bool, schedule_enabled: bool) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔌 Подключить", callback_data="connect")
    kb.button(text="♻️ Переподключить", callback_data="reconnect")
    kb.button(text="❌ Отключить", callback_data="disconnect")
    kb.button(
        text=f"👁 Passthrough: {'ON' if passthrough else 'OFF'}",
        callback_data="toggle_passthrough",
    )
    kb.button(
        text=f"⏰ Авто /buff: {'ON' if schedule_enabled else 'OFF'}",
        callback_data="toggle_schedule",
    )
    kb.button(text="🕒 Время /buff", callback_data="set_time")
    kb.button(text="ℹ️ Статус", callback_data="status")
    kb.adjust(2, 2, 2, 1)
    return kb
