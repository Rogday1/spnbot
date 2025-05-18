from aiogram.filters.callback_data import CallbackData


class AdminCallback(CallbackData, prefix="admin"):
    """
    Класс для работы с callback-данными админ-панели
    """
    action: str
    value: str = "" 