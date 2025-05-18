from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.db import async_session
from src.database.repositories import UserRepository


class UserDBMiddleware(BaseMiddleware):
    """
    Middleware для автоматического сохранения пользователей в базе данных
    при любом взаимодействии с ботом.
    """
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем данные пользователя из события
        user = event.from_user
        
        if user:
            try:
                # Создаём сессию базы данных
                async with async_session() as session:
                    # Создаём репозиторий пользователей
                    user_repo = UserRepository(session)
                    
                    # Получаем или создаём пользователя в БД
                    db_user = await user_repo.get_user(user.id)
                    
                    # Обновляем имя и юзернейм, если они изменились
                    if db_user.first_name != user.first_name or db_user.username != user.username:
                        db_user.first_name = user.first_name
                        db_user.username = user.username
                        if user.last_name is not None:
                            db_user.last_name = user.last_name
                        
                        # Если никнейм еще не установлен, используем имя из Telegram
                        if not db_user.nickname:
                            db_user.nickname = user.first_name
                        
                        await user_repo.update_user(db_user)
                        
                        logging.info(f"Обновлен профиль пользователя {user.id} в базе данных")
            
            except Exception as e:
                logging.error(f"Ошибка при сохранении пользователя в БД: {e}")
        
        # Продолжаем обработку события
        return await handler(event, data) 