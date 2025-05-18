from aiogram import Dispatcher, Router
from .start import router as start_router
from .admin import router as admin_router
import logging

def register_all_handlers(dp: Dispatcher) -> None:
    """
    Регистрирует все обработчики сообщений в диспетчере.
    
    Args:
        dp (Dispatcher): Диспетчер, в котором регистрируются обработчики
    """
    # Теперь каждый роутер строго фильтрует только свои команды и обработчики
    # Порядок регистрации больше не должен влиять на обработку команд
    
    logging.info("Регистрация обработчиков бота...")
    
    # Регистрируем обработчик admin команд
    dp.include_router(admin_router)
    logging.info("Зарегистрирован роутер admin_commands")
    
    # Регистрируем обработчик start команд и общих сообщений
    dp.include_router(start_router)
    logging.info("Зарегистрирован роутер start_commands")
    
    logging.info("Все обработчики зарегистрированы успешно")
