from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
import os
from typing import Union, Dict, Any
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class AdminFilter(BaseFilter):
    """
    Фильтр для проверки, является ли пользователь администратором
    """
    
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        """
        Выполняет проверку на администратора
        
        Args:
            event (Union[Message, CallbackQuery]): Событие от пользователя
            
        Returns:
            bool: True, если пользователь администратор, иначе False
        """
        # Определяем ID пользователя в зависимости от типа события
        user_id = event.from_user.id
        
        # Получаем список ID администраторов из переменной окружения
        admins_str = os.getenv("ADMINS_ID", "")
        
        # Проверяем, есть ли администраторы в переменной окружения
        if not admins_str:
            return False
            
        # Преобразуем строку с ID администраторов в список целых чисел
        admin_ids = [int(admin_id.strip()) for admin_id in admins_str.split(",") if admin_id.strip()]
        
        # Проверяем, является ли пользователь администратором
        return user_id in admin_ids 