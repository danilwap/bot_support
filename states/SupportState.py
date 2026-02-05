from aiogram.fsm.state import State, StatesGroup


class SupportState(StatesGroup):
    send_request = State()
    in_support = State()
