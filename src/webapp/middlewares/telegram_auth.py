import hmac
import hashlib
import time
import json
from urllib.parse import parse_qs
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from src.config import settings

class TelegramAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware для проверки авторизации Telegram WebApp.
    Реализует безопасную проверку данных в соответствии с документацией Telegram.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.secret_key = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()
        self.excluded_paths = [
            '/docs', '/redoc', '/openapi.json',
            '/', '/game', '/api/user/check_subscription',
            '/favicon.ico'
        ]
        self.excluded_prefixes = ['/static/']
        
    async def dispatch(self, request: Request, call_next):
        # Пропускаем проверку для исключенных путей и префиксов
        if (any(request.url.path == path for path in self.excluded_paths) or
            any(request.url.path.startswith(prefix) for prefix in self.excluded_prefixes)):
            return await call_next(request)
            
        # В режиме DEBUG пропускаем проверку
        if settings.DEBUG:
            request.state.user_id = 1  # Тестовый ID для разработки
            return await call_next(request)
            
        # Получаем данные авторизации
        init_data = request.headers.get("X-Telegram-Init-Data")
        if not init_data:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Отсутствуют данные авторизации Telegram"
            )
            
        try:
            # Валидируем данные и получаем user_id
            user_id = self.validate_telegram_data(init_data)
            request.state.user_id = user_id
            return await call_next(request)
        except ValueError as e:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        except Exception:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="Ошибка проверки авторизации"
            )
            
    def validate_telegram_data(self, init_data: str) -> int:
        """
        Валидирует данные Telegram WebApp и возвращает user_id
        
        Args:
            init_data: Строка с данными авторизации
            
        Returns:
            user_id: Идентификатор пользователя
            
        Raises:
            ValueError: При ошибках валидации
        """
        # Парсим данные
        parsed = parse_qs(init_data)
        
        # Проверяем обязательные поля
        required_fields = ['auth_date', 'hash', 'user']
        if not all(field in parsed for field in required_fields):
            raise ValueError("Отсутствуют обязательные поля в данных авторизации")
            
        # Проверяем срок действия (максимум 24 часа)
        auth_time = int(parsed['auth_date'][0])
        if time.time() - auth_time > 86400:
            raise ValueError("Данные авторизации устарели")
            
        # Извлекаем хеш для проверки
        received_hash = parsed['hash'][0]
        
        # Формируем строку для проверки
        data_check = []
        for key in sorted(parsed.keys()):
            if key == 'hash':
                continue
            # Telegram использует первый элемент массива значений
            data_check.append(f"{key}={parsed[key][0]}")
        data_check_string = "\n".join(data_check)
        
        # Вычисляем HMAC
        computed_hash = hmac.new(
            self.secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Сравниваем хеши с защитой от timing-атак
        if not hmac.compare_digest(computed_hash, received_hash):
            raise ValueError("Недействительная подпись данных")
            
        # Извлекаем и проверяем данные пользователя
        try:
            user_data = json.loads(parsed['user'][0])
            user_id = user_data.get('id')
            if not user_id or not isinstance(user_id, int):
                raise ValueError("Некорректный ID пользователя")
            return user_id
        except json.JSONDecodeError:
            raise ValueError("Ошибка формата данных пользователя")