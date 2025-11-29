from aiogram.fsm.state import State, StatesGroup


class ConnectStates(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()


class TimeState(StatesGroup):
    waiting_time = State()
