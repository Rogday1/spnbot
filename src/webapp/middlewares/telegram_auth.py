import hmac
import hashlib
import time
from typing import Optional, Dict, List, Callable, Any
from urllib.parse import parse_qs
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from src.config import settings
import logging
import json
import re

logger = logging.getLogger(__name__)

class TelegramAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware для проверки авторизации Telegram WebApp.
    
    Проверяет X-Telegram-Init-Data заголовок запроса и валидирует его подпись
    с использованием секретного токена бота.
    Обеспечивает дополнительную защиту от CSRF и других атак.
    """
    
    def __init__(
        self, 
        app, 
        bot_token: str = None,
        exclude_paths: List[str] = None,
        exclude_prefixes: List[str] = None
    ):
        """
        Инициализирует middleware для проверки авторизации Telegram WebApp.
        
        Args:
            app: FastAPI приложение
            bot_token (str, optional): Токен бота для проверки подписи. По умолчанию берется из настроек.
            exclude_paths (List[str], optional): Список путей, которые не требуют аутентификации.
            exclude_prefixes (List[str], optional): Список префиксов путей, которые не требуют аутентификации.
        """
        super().__init__(app)
        self.bot_token = bot_token or settings.BOT_TOKEN
        
        # Генерируем секретный ключ с проверкой
        if not self.bot_token:
            logging.error("Критическая ошибка: BOT_TOKEN не указан для TelegramAuthMiddleware")
            raise ValueError("BOT_TOKEN не может быть пустым для TelegramAuthMiddleware")
            
        self.secret_key = hashlib.sha256(self.bot_token.encode()).digest()
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/", "/game"]
        self.exclude_prefixes = exclude_prefixes or ["/static/"]
        
        # Максимальное допустимое время действия авторизации (24 часа)
        self.max_auth_age = 86400
        
        logger.info("TelegramAuthMiddleware инициализирован")
        if settings.DEBUG:
            logger.debug(f"DEBUG: BOT_TOKEN (хеш): {hashlib.sha256(self.bot_token.encode()).hexdigest()}")
            logger.debug(f"DEBUG: WEBAPP_PUBLIC_URL: {settings.WEBAPP_PUBLIC_URL}")
    
    async def dispatch(self, request: Request, call_next: Callable):
        """
        Обрабатывает каждый HTTP запрос и проверяет авторизацию.
        
        Args:
            request (Request): Объект запроса
            call_next (Callable): Функция для передачи запроса дальше
            
        Returns:
            Response: Ответ от следующего обработчика или ошибка авторизации
        """
        # Сохраняем путь для логирования
        path = request.url.path
        
        try:
            # Проверяем Path до проверки auth - это более эффективно
            if self._should_skip_auth(path):
                return await call_next(request)
            
            # Проверяем, что метод запроса безопасный (для небезопасных методов нужна CSRF-защита)
            is_safe_method = request.method in ["GET", "HEAD", "OPTIONS"]
            
            # Проверяем наличие инициализационных данных
            init_data = request.headers.get("X-Telegram-Init-Data")
            
            # Проверяем заголовки для защиты от CSRF
            origin = request.headers.get("Origin")
            referer = request.headers.get("Referer")
            
            # Заменить это условие
            if settings.DEBUG:
                logger.debug(...)
                
            # На это условие
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"DEBUG: Получен запрос на путь: {path}, Метод: {request.method}")
                logger.debug(f"DEBUG: Значение X-Telegram-Init-Data: {init_data}")
                logger.debug(f"DEBUG: Origin: {origin}, Referer: {referer}")

            # Проверяем заголовки для защиты от CSRF
            is_valid_origin = False
            is_valid_referer = False
            
            # В методе dispatch класса TelegramAuthMiddleware
            
            # Список разрешенных источников для Telegram WebApp
            allowed_origins = ["https://telegram.org", "https://t.me", "https://tgspin.ru"]
            
            # Если заданы CORS_ORIGINS в настройках, используем их
            if hasattr(settings, "CORS_ORIGINS") and settings.CORS_ORIGINS:
                allowed_origins.extend(settings.CORS_ORIGINS)
            
            # Удаляем дубликаты
            allowed_origins = list(set(allowed_origins))
            
            # Проверяем Origin
            if origin:
                is_valid_origin = any(origin.startswith(allowed) for allowed in allowed_origins)
            
            # Проверяем Referer
            if referer:
                is_valid_referer = any(referer.startswith(allowed) for allowed in allowed_origins)
            
            # В режиме разработки проверки более лояльные
            if settings.DEBUG:
                # В режиме отладки позволяем запросы без аутентификации для упрощения тестирования
                if not init_data:
                    logging.warning(f"Пропуск аутентификации в режиме разработки для: {path} (Init Data отсутствует)")
                    return await call_next(request)
                
                # Проверяем Origin и Referer только в режиме отладки для диагностики
                if origin and not is_valid_origin and origin != "null":
                    logging.warning(f"Подозрительный Origin в режиме разработки: {origin} (не в разрешенных)")
                
                if referer and not is_valid_referer:
                    logging.warning(f"Подозрительный Referer в режиме разработки: {referer} (не в разрешенных)")
                
                # Если данные есть, но они некорректны, все равно пытаемся их проверить
                # чтобы логировать потенциальные проблемы
                if init_data:
                    validation_result = self._validate_telegram_data(init_data)
                    if not validation_result['valid']:
                        logging.warning(f"Некорректные данные авторификации в режиме разработки: {validation_result['error']}")
                        logger.debug(f"DEBUG: Невалидные Init Data: {init_data}")
                    else:
                        logger.debug("DEBUG: Init Data успешно валидированы в режиме разработки.")
                    
                    # Устанавливаем user_id в состоянии запроса для обработчиков
                    if validation_result.get('user_id'):
                        request.state.user_id = validation_result['user_id']
                    
                    # В любом случае пропускаем запрос в режиме отладки
                    return await call_next(request)
            
            # В продакшн-режиме выполняем полные проверки
            
            # 1. Проверяем заголовки для защиты от CSRF (только для небезопасных методов)
            if not is_safe_method:
                # Для POST, PUT, DELETE и других изменяющих методов нужна строгая проверка CSRF
                valid_headers = is_valid_origin or is_valid_referer
                
                if not valid_headers:
                    logging.error(f"CSRF-проверка не пройдена для {request.method} запроса на {path}. Origin: {origin}, Referer: {referer}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Защита от CSRF: недопустимый источник запроса"
                    )
            
            # 2. Проверяем наличие инициализационных данных
            if not init_data:
                client_ip = request.client.host if request.client else "неизвестно"
                user_agent = request.headers.get("User-Agent", "неизвестно")
                logger.warning(f"Отсутствуют данные инициализации Telegram для: {path}. IP: {client_ip}, User-Agent: {user_agent}")
                
                # Возвращаем ошибку с минимумом деталей для безопасности
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Отсутствуют данные авторизации Telegram WebApp"
                )
            
            # 3. Валидируем данные с защитой от различных типов атак
            try:
                validation_result = self._validate_telegram_data(init_data)
                if settings.DEBUG:
                    logger.debug(f"DEBUG: Результат валидации init_data: {validation_result}")
            except Exception as e:
                # Добавляем детальное логирование для отладки
                logging.error(f"Исключение при валидации данных Telegram: {e} для пути {path}")
                # Возвращаем общую ошибку без деталей для безопасности
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Ошибка проверки данных авторизации"
                )
            
            if not validation_result['valid']:
                client_ip = request.client.host if request.client else "неизвестно"
                error_msg = validation_result.get('error', 'Неизвестная ошибка')
                logger.error(f"Ошибка валидации данных Telegram: {error_msg} для пути {path}. IP: {client_ip}")
                if settings.DEBUG:
                    logger.debug(f"DEBUG: Невалидные Init Data: {init_data}")
                
                # Возвращаем обобщенную ошибку для пользователя
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, 
                    detail="Недействительные данные авторизации"
                )
            
            # Устанавливаем user_id в состоянии запроса для обработчиков
            if validation_result.get('user_id'):
                request.state.user_id = validation_result['user_id']
            
            # 4. Проверяем, соответствует ли идентификатор пользователя в URL тому, что в initData
            user_id_from_data = validation_result.get('user_id')
            
            if user_id_from_data:
                # Извлекаем ID пользователя из пути URL с помощью регулярного выражения
                # Ищем паттерны вида /users/123, /api/user/123/profile, и т.д.
                user_id_match = re.search(r'/(?:users?|user_id)/(\d+)(?:/|$)', path)
                
                if user_id_match:
                    try:
                        path_user_id = int(user_id_match.group(1))
                        
                        # Сравниваем с ID из данных авторизации
                        if path_user_id != user_id_from_data:
                            client_ip = request.client.host if request.client else "неизвестно"
                            logger.error(f"Несоответствие ID пользователя: {path_user_id} != {user_id_from_data} для пути {path}. IP: {client_ip}")
                            
                            # Возвращаем ошибку доступа без раскрытия деталей
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Доступ запрещен"
                            )
                    except ValueError:
                        # Если ID в URL не может быть преобразован в int
                        logger.error(f"Некорректный формат ID пользователя в URL: {user_id_match.group(1)}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Некорректный формат ID пользователя"
                        )
            
            # 5. Если всё в порядке, продолжаем обработку запроса
            try:
                response = await call_next(request)
                return response
            except Exception as e:
                # Логируем ошибку, но не раскрываем детали клиенту
                logging.error(f"Ошибка при обработке запроса после аутентификации: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Внутренняя ошибка сервера"
                )
        except HTTPException:
            # Пробрасываем HTTPException без изменений
            raise
        except Exception as e:
            # Логируем любые другие исключения и возвращаем общую ошибку
            logging.exception(f"Необработанное исключение в TelegramAuthMiddleware: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка сервера при проверке авторизации"
            )
    
    def _should_skip_auth(self, path: str) -> bool:
        """
        Проверяет, следует ли пропустить аутентификацию для данного пути.
        
        Args:
            path (str): Путь запроса
            
        Returns:
            bool: True, если аутентификацию следует пропустить, иначе False
        """
        # Проверяем точные совпадения
        if path in self.exclude_paths:
            return True
        
        # Проверяем префиксы
        for prefix in self.exclude_prefixes:
            if path.startswith(prefix):
                return True
        
        return False
    
    def _validate_telegram_data(self, init_data: str) -> Dict[str, Any]:
        """
        Валидирует данные инициализации Telegram WebApp.
        
        Args:
            init_data (str): Данные инициализации из X-Telegram-Init-Data
            
        Returns:
            Dict: Результат валидации с ключами valid, error, user_id
        """
        try:
            # В режиме DEBUG всегда возвращаем успешную валидацию
            if settings.DEBUG:
                # Пытаемся извлечь user_id для логов
                try:
                    parsed_data = parse_qs(init_data)
                    # Извлекаем user_id для использования в запросах
                    user_id = None
                    try:
                        # Пытаемся извлечь user_id из данных
                        if parsed_data and 'user' in parsed_data and parsed_data['user']:
                            user_data = parsed_data['user']
                            if isinstance(user_data, dict) and 'id' in user_data:
                                user_id = user_data['id']
                    except Exception as e:
                        logger.warning(f"Не удалось извлечь user_id из данных: {e}")
                    
                    # В режиме отладки всегда возвращаем valid=True для упрощения тестирования
                    if settings.DEBUG:
                        # Но все равно возвращаем user_id, если он был извлечен
                        return {'valid': True, 'user_id': user_id}
                    
                    # Просто логируем, но не блокируем запрос в режиме отладки
                    if 'hash' not in parsed_data:
                        logging.warning(f"DEBUG: Отсутствует хеш в данных для пользователя {user_id}")
                except Exception as e:
                    logging.warning(f"DEBUG: Ошибка при разборе данных: {e}")
                
                # В режиме отладки всегда считаем валидным
                return {'valid': True, 'error': None, 'user_id': None}
            
            # Проверяем, что init_data не пустой и имеет допустимый формат
            if not init_data:
                return {'valid': False, 'error': 'Пустые данные инициализации', 'user_id': None}
            
            if not isinstance(init_data, str):
                return {'valid': False, 'error': 'Данные инициализации должны быть строкой', 'user_id': None}
            
            # Проверяем на наличие недопустимых символов (защита от инъекций)
            if re.search(r'[^\w\d\s&=\-_.,%:/@\[\]\{\}+]', init_data):
                return {'valid': False, 'error': 'Недопустимые символы в данных инициализации', 'user_id': None}
            
            # Проверяем максимальную длину данных для предотвращения DoS
            if len(init_data) > 10000:  # Ограничение на 10KB
                return {'valid': False, 'error': 'Слишком большой объем данных инициализации', 'user_id': None}
            
            # Разбираем данные с защитой от ошибок
            try:
                parsed_data = parse_qs(init_data)
            except Exception as e:
                return {'valid': False, 'error': f'Ошибка при разборе данных инициализации: {str(e)}', 'user_id': None}
            
            # Проверяем минимальный набор необходимых параметров
            required_params = ['auth_date', 'hash', 'user']
            for param in required_params:
                if param not in parsed_data or not parsed_data[param]:
                    return {'valid': False, 'error': f'Отсутствует обязательный параметр: {param}', 'user_id': None}
            
            # Получаем параметры для проверки
            received_hash = parsed_data['hash'][0]
            auth_date = parsed_data['auth_date'][0]
            
            # Проверяем формат хеша на соответствие
            if not re.match(r'^[a-f0-9]{64}$', received_hash):
                return {'valid': False, 'error': 'Некорректный формат хеша', 'user_id': None}
            
            # Проверяем, что auth_date - числовое значение
            if not auth_date.isdigit():
                return {'valid': False, 'error': 'Некорректная дата авторизации', 'user_id': None}
            
            # Проверяем, не устарела ли авторизация (max 24 часа)
            try:
                auth_time = int(auth_date)
                current_time = int(time.time())
                
                if current_time < auth_time:
                    # Дата авторизации в будущем - явно ошибка
                    return {'valid': False, 'error': 'Дата авторизации в будущем', 'user_id': None}
                
                if current_time - auth_time > self.max_auth_age:
                    return {'valid': False, 'error': 'Данные авторизации устарели', 'user_id': None}
            except ValueError:
                return {'valid': False, 'error': 'Ошибка при проверке времени авторизации', 'user_id': None}
            
            # Формируем проверочную строку (без hash)
            try:
                # Исключаем 'hash' и 'signature' из данных для формирования строки проверки
                check_string = '\n'.join(
                    f"{k}={v[0]}" for k, v in sorted(parsed_data.items())
                    if k not in ['hash', 'signature']
                )
            except Exception as e:
                logging.error(f"Ошибка при формировании проверочной строки: {e}")
                return {'valid': False, 'error': 'Ошибка при формировании строки для проверки подписи', 'user_id': None}
            
            # Вычисляем хеш с защитой от ошибок
            try:
                computed_hash = hmac.new(
                    self.secret_key,
                    check_string.encode(),
                    hashlib.sha256
                ).hexdigest()
            except Exception as e:
                logging.error(f"Ошибка при вычислении хеша: {e}")
                return {'valid': False, 'error': 'Ошибка при вычислении подписи', 'user_id': None}
            
            # Проверяем хеш с защитой от timing-атак
            if not hmac.compare_digest(computed_hash, received_hash):
                return {'valid': False, 'error': 'Недействительная подпись данных', 'user_id': None}
            
            # Извлекаем и проверяем данные пользователя
            user_id = None
            try:
                if 'user' in parsed_data:
                    user_data_str = parsed_data['user'][0]
                    if not user_data_str:
                        return {'valid': False, 'error': 'Пустой объект пользователя', 'user_id': None}
                    
                    # Проверяем формат JSON
                    if not user_data_str.startswith('{') or not user_data_str.endswith('}'):
                        return {'valid': False, 'error': 'Некорректный формат JSON объекта пользователя', 'user_id': None}
                    
                    # Проверяем максимальный размер данных пользователя
                    if len(user_data_str) > 2000:  # Ограничение 2KB
                        return {'valid': False, 'error': 'Слишком большой объем данных пользователя', 'user_id': None}
                    
                    # Парсим JSON
                    user_data = json.loads(user_data_str)
                    
                    # Проверяем обязательные поля пользователя
                    user_id = user_data.get('id')
                    
                    # Telegram всегда предоставляет ID пользователя в WebApp
                    if not user_id:
                        return {'valid': False, 'error': 'Отсутствует ID пользователя', 'user_id': None}
                    
                    # Проверяем, что ID пользователя является числом и больше 0
                    if not isinstance(user_id, int) or user_id <= 0:
                        return {'valid': False, 'error': 'Некорректный ID пользователя', 'user_id': None}
            except json.JSONDecodeError as e:
                return {'valid': False, 'error': f'Некорректный формат данных пользователя: {e}', 'user_id': None}
            except Exception as e:
                logging.error(f"Ошибка при извлечении ID пользователя: {e}")
                return {'valid': False, 'error': f'Ошибка при обработке данных пользователя: {str(e)}', 'user_id': None}
            
            # Дополнительные проверки данных пользователя
            if 'query_id' in parsed_data and parsed_data['query_id'][0]:
                # Если указан query_id, значит, запрос был через Telegram.WebApp.sendData,
                # в таком случае нам нужно дополнительно проверить валидность формата
                query_id = parsed_data['query_id'][0]
                if not query_id.isalnum() or len(query_id) > 64:
                    return {'valid': False, 'error': 'Некорректный формат query_id', 'user_id': user_id}
            
            return {'valid': True, 'error': None, 'user_id': user_id}
            
        except Exception as e:
            # Защищаем от непредвиденных ошибок
            logging.exception(f"Непредвиденная ошибка при валидации данных Telegram: {e}")
            return {'valid': False, 'error': 'Внутренняя ошибка валидации', 'user_id': None}