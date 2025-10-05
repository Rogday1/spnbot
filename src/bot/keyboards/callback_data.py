from aiogram.filters.callback_data import CallbackData
from typing import Optional


class AdminCallback(CallbackData, prefix="admin"):
    """
    Класс для работы с callback-данными админ-панели
    """
    action: str
    value: Optional[str] = None 