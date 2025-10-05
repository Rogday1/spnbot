from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union
import logging

class AdminFilter(BaseFilter):
    """
    Фильтр для проверки, является ли пользователь администратором
    Проверяет права администратора по базе данных (поле is_admin)
    """
    
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        """
        Выполняет проверку на администратора через базу данных
        
        Args:
            event (Union[Message, CallbackQuery]): Событие от пользователя
            
        Returns:
            bool: True, если пользователь администратор, иначе False
        """
        user_id = None
        try:
            # Определяем ID пользователя в зависимости от типа события
            user_id = event.from_user.id
            
            # Импортируем здесь, чтобы избежать циклических импортов
            from src.database.db import get_session
            from src.database.repositories.user_repository import UserRepository
            
            # Проверяем права администратора в базе данных
            async for session in get_session():
                user_repo = UserRepository(session)
                user = await user_repo.get_user(user_id)
                
                if user and user.is_admin:
                    logging.info(f"✓ Пользователь {user_id} является администратором")
                    return True
                else:
                    logging.warning(f"✗ Пользователь {user_id} НЕ является администратором (user={user}, is_admin={user.is_admin if user else 'None'})")
                    return False
                    
        except Exception as e:
            logging.error(f"✗ Ошибка при проверке прав администратора для пользователя {user_id}: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return False 