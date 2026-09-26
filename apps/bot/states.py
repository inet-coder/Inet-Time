from aiogram.fsm.state import State, StatesGroup


class QrLogin(StatesGroup):
    waiting_password = State()


class PhoneLogin(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()


class EditTemplate(StatesGroup):
    waiting_text = State()


class Topup(StatesGroup):
    waiting_amount = State()
