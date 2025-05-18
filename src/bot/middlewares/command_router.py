from typing import Dict, Any, Awaitable, Callable, Set
from aiogram import BaseMiddleware
from aiogram.types import Message
import logging

class CommandRouterMiddleware(BaseMiddleware):
    """
    Middleware для корректной маршрутизации команд между различными обработчиками.
    Помогает избежать конфликтов между разными роутерами.
    """
    # Словарь соответствия команд и роутеров
    COMMAND_ROUTER_MAP = {
        'admin': 'admin_commands',  # Команда /admin обрабатывается роутером admin_commands
        'start': 'start_commands',   # Команда /start обрабатывается роутером start_commands
        # Можно добавить другие команды
    }
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обрабатывает сообщения перед их передачей хендлерам и помогает
        корректно перенаправлять команды нужным обработчикам.

        Args:
            handler (Callable): Обработчик сообщения
            event (Message): Объект сообщения
            data (Dict[str, Any]): Данные для обработчика

        Returns:
            Any: Результат обработки сообщения
        """
        current_router_name = data.get('event_router')
        logging.info(f"CommandRouterMiddleware: Получено сообщение в роутере '{current_router_name}'")
        
        # Проверяем, является ли сообщение командой
        if event.text and event.text.startswith('/'):
            # Получаем команду без слеша и аргументов
            command = event.text.split()[0][1:].lower()
            target_router = self.COMMAND_ROUTER_MAP.get(command)
            
            logging.info(f"CommandRouterMiddleware: Обнаружена команда '/{command}'. Текущий роутер: '{current_router_name}', целевой роутер: '{target_router}'")
            
            # Если для команды определен специальный роутер
            if target_router:
                # Если текущий роутер не соответствует целевому
                if current_router_name != target_router:
                    logging.info(f"CommandRouterMiddleware: Команда '/{command}' должна обрабатываться роутером '{target_router}', а не '{current_router_name}'. Пропускаем.")
                    return None
                else:
                    logging.info(f"CommandRouterMiddleware: Команда '/{command}' будет обрабатываться в правильном роутере '{current_router_name}'")
            else:
                logging.info(f"CommandRouterMiddleware: Для команды '/{command}' не определен специальный роутер. Продолжаем обработку.")
        else:
            logging.info(f"CommandRouterMiddleware: Сообщение не является командой. Продолжаем обработку.")
        
        # Выполняем обработчик, если это не команда или если это правильный роутер для команды
        result = await handler(event, data)
        logging.info(f"CommandRouterMiddleware: Обработка завершена в роутере '{current_router_name}'")
        return result 