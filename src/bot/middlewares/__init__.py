from aiogram import Dispatcher
from .user_db import UserDBMiddleware
import logging

def setup_middlewares(dp: Dispatcher):
    """
    Настройка middleware для диспетчера сообщений
    
    Args:
        dp (Dispatcher): Диспетчер сообщений
    """
    logging.info("Настройка middleware для диспетчера сообщений")
    
    # Регистрируем middleware для работы с базой данных пользователей
    dp.message.middleware.register(UserDBMiddleware())
    dp.callback_query.middleware.register(UserDBMiddleware())
    logging.info("Зарегистрирован UserDBMiddleware")
