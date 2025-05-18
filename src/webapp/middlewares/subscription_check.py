from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging
import json
from typing import List, Dict, Any, Optional

from src.config import settings
from src.bot.utils.subscription import check_all_subscriptions


class SubscriptionCheckMiddleware(BaseHTTPMiddleware):
    """
    Middleware для проверки подписки пользователя на обязательные каналы.
    Блокирует доступ к API игры для пользователей, не подписанных на каналы.
    """
    
    def __init__(
        self,
        app,
        bot_instance=None,
        api_path_prefix: str = "/api/spin/",
        exclude_paths: List[str] = None,
        exclude_prefixes: List[str] = None,
    ):
        super().__init__(app)
        self.bot_instance = bot_instance
        self.api_path_prefix = api_path_prefix
        self.exclude_paths = exclude_paths or []
        self.exclude_prefixes = exclude_prefixes or []
        
    async def dispatch(self, request: Request, call_next):
        """
        Проверяет подписку пользователя перед доступом к API игры.
        
        Args:
            request (Request): Объект запроса
            call_next: Следующий обработчик в цепочке middleware
            
        Returns:
            Response: Ответ сервера
        """
        # Пропускаем пути, которые не нужно проверять
        path = request.url.path
        
        # Если путь исключен из проверки, пропускаем
        if path in self.exclude_paths:
            return await call_next(request)
            
        # Если путь начинается с префикса, который исключен, пропускаем
        for prefix in self.exclude_prefixes:
            if path.startswith(prefix):
                return await call_next(request)
        
        # Проверяем только пути к API игры
        if not path.startswith(self.api_path_prefix):
            return await call_next(request)
            
        # Проверяем, нужно ли проверять подписку (настройка REQUIRED_CHANNELS)
        if not settings.REQUIRED_CHANNELS:
            return await call_next(request)
        
        # Проверяем наличие экземпляра бота
        if not self.bot_instance:
            logging.error("Экземпляр бота не передан в SubscriptionCheckMiddleware")
            return await call_next(request)
        
        # Получаем ID пользователя из URL
        try:
            # Примерный путь: /api/spin/123456789
            user_id_str = path.split('/')[-1].split('?')[0]  # Извлекаем ID, отбрасывая query params
            user_id = int(user_id_str)
        except (ValueError, IndexError):
            # Если не удалось получить ID пользователя, пропускаем запрос
            # Это может быть другой API endpoint
            return await call_next(request)
        
        # Проверяем подписку пользователя
        try:
            all_subscribed, _ = await check_all_subscriptions(self.bot_instance, user_id)
            
            if not all_subscribed:
                # Если пользователь не подписан, блокируем доступ
                return JSONResponse(
                    status_code=403,
                    content={
                        "success": False,
                        "message": "Для доступа к игре необходимо подписаться на все обязательные каналы. Вернитесь в бота и пройдите верификацию."
                    }
                )
                
            # Если подписан, пропускаем запрос дальше
            return await call_next(request)
            
        except Exception as e:
            logging.error(f"Ошибка при проверке подписки: {e}")
            # В случае ошибки пропускаем запрос (не блокируем)
            return await call_next(request) 