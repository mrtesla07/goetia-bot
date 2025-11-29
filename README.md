# Goetia Bot

Сервис-бот для подключения пользовательских аккаунтов через my.telegram.org/apps (MTProto), пересылки сообщений с @Agent_essence_bot и обратной отправки, а также ежедневной команды `/buff` по расписанию.

## Быстрый старт
1. `python -m venv .venv && .venv\Scripts\activate`
2. `pip install -r requirements.txt`
3. Скопируйте `.env.example` в `.env` и заполните `BOT_TOKEN`, `API_ID`, `API_HASH` (при необходимости `TZ`, по умолчанию Europe/Moscow).
4. `python main.py` — запуск бота. Данные сохраняются в `data/goetia.db`, сессии Telethon — в `sessions/`.

## Функционал
- Подключение аккаунта через MTProto (код подтверждения + опционально 2FA).
- Пересылка сообщений от @Agent_essence_bot пользователю и обратная отправка.
- Режим passthrough: пересылка сообщений только от @Agent_essence_bot (другие чаты игнорируются).
- Ежедневная авто-команда `/buff` по МСК, время настраивается.
- Инлайн-меню для всего функционала (подключение, отключение, расписание, passthrough, статус).

## Структура
- `src/goetia_bot` — исходники бота.
- `data/` — база SQLite.
- `sessions/` — сессии MTProto-подключений пользователей.
