import hmac
import hashlib
import time
from typing import List, Optional, Callable, Dict, Any
from urllib.parse import parse_qs, unquote
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from src.config import settings
import logging
import json

logger = logging.getLogger(__name__)

class TelegramAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware для проверки авторизации Telegram WebApp.
    Реализует проверку подписи данных согласно официальной документации.
    """

    def __init__(
        self, 
        app, 
        bot_token: str = None,
        exclude_paths: List[str] = None,
        exclude_prefixes: List[str] = None
    ):
        super().__init__(app)
        self.bot_token = bot_token or settings.BOT_TOKEN
        
        if not self.bot_token:
            logger.error("BOT_TOKEN не указан для TelegramAuthMiddleware")
            raise ValueError("BOT_TOKEN обязателен для TelegramAuthMiddleware")
            
        # Генерация секретного ключа из токена бота
        self.secret_key = hashlib.sha256(self.bot_token.encode()).digest()
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json"]
        self.exclude_prefixes = exclude_prefixes or ["/static/"]
        self.max_auth_age = 86400  # 24 часа

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        
        if self._should_skip_auth(path):
            return await call_next(request)
            
        init_data_raw = request.headers.get("X-Telegram-Init-Data")
        if not init_data_raw:
            logger.warning("Отсутствует X-Telegram-Init-Data")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Требуется авторизация Telegram"
            )

        try:
            # Валидация данных
            validation_result = self.validate_telegram_data(init_data_raw)
            
            if not validation_result["valid"]:
                logger.error(f"Ошибка валидации: {validation_result.get('error')}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недействительные данные авторизации"
                )
                
            # Установка user_id в состояние запроса
            if user_id := validation_result.get("user_id"):
                request.state.user_id = user_id
                
        except Exception as e:
            logger.exception(f"Ошибка при валидации: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка обработки авторизации"
            )

        return await call_next(request)

    def _should_skip_auth(self, path: str) -> bool:
        """Проверяет исключения для путей"""
        if path in self.exclude_paths:
            return True
        return any(path.startswith(prefix) for prefix in self.exclude_prefixes)

    def validate_telegram_data(self, init_data_raw: str) -> Dict[str, Any]:
        """
        Валидирует данные Telegram WebApp согласно документации:
        https://core.telegram.org/widgets/login
        """
        try:
            # Парсинг query-строки
            parsed_data = parse_qs(init_data_raw)
            
            # Проверка обязательных полей
            required = ["hash", "auth_date", "user"]
            for field in required:
                if field not in parsed_data or not parsed_data[field]:
                    return {"valid": False, "error": f"Отсутствует поле: {field}"}

            telegram_hash = parsed_data["hash"][0]
            auth_date = parsed_data["auth_date"][0]
            user_data = parsed_data["user"][0]

            # Проверка временной метки
            try:
                auth_time = int(auth_date)
                if time.time() - auth_time > self.max_auth_age:
                    return {"valid": False, "error": "Данные авторизации устарели"}
            except ValueError:
                return {"valid": False, "error": "Неверный формат времени авторизации"}

            # Формирование data_check_string
            data_check_list = []
            for key, values in parsed_data.items():
                if key == "hash":
                    continue
                # Используем первое значение для каждого ключа
                value = values[0] if values else ""
                data_check_list.append(f"{key}={value}")
                
            data_check_list.sort()
            data_check_string = "\n".join(data_check_list)

            # Генерация HMAC
            secret_key = hashlib.sha256(self.bot_token.encode()).digest()
            computed_hash = hmac.new(
                secret_key,
                data_check_string.encode(),
                hashlib.sha256
            ).hexdigest()

            # Безопасное сравнение хешей
            if not hmac.compare_digest(computed_hash, telegram_hash):
                return {"valid": False, "error": "Несовпадение хешей"}

            # Извлечение user_id
            try:
                user = json.loads(user_data)
                user_id = user.get("id")
                if not user_id:
                    return {"valid": False, "error": "Отсутствует ID пользователя"}
            except json.JSONDecodeError:
                return {"valid": False, "error": "Ошибка парсинга данных пользователя"}

            return {"valid": True, "user_id": user_id}

        except Exception as e:
            logger.error(f"Ошибка валидации: {str(e)}")
            return {"valid": False, "error": f"Системная ошибка: {str(e)}"}