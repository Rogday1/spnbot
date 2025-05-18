import time
from typing import Dict, List, Callable, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from collections import defaultdict

class RateLimiter:
    """
    Класс для отслеживания частоты запросов от клиентов.
    Использует алгоритм "скользящее окно" для более точного ограничения.
    """
    
    def __init__(self, window_size: int = 60, max_requests: int = 30):
        """
        Инициализирует лимитер с заданными параметрами.
        
        Args:
            window_size (int): Размер временного окна в секундах
            max_requests (int): Максимальное количество запросов в окне
        """
        self.window_size = window_size
        self.max_requests = max_requests
        self.clients: Dict[str, List[float]] = defaultdict(list)
    
    def is_allowed(self, client_id: str) -> Tuple[bool, Dict]:
        """
        Проверяет, разрешено ли клиенту выполнить запрос.
        
        Args:
            client_id (str): Идентификатор клиента
        
        Returns:
            Tuple[bool, Dict]: (разрешено, информация о лимите)
        """
        current_time = time.time()
        
        # Удаляем запросы, которые находятся за пределами временного окна
        self.clients[client_id] = [
            timestamp for timestamp in self.clients[client_id] 
            if current_time - timestamp < self.window_size
        ]
        
        # Получаем текущее количество запросов в окне
        current_count = len(self.clients[client_id])
        
        # Проверяем, не превышен ли лимит
        if current_count >= self.max_requests:
            # Вычисляем, когда клиент сможет сделать следующий запрос
            oldest_request = min(self.clients[client_id]) if self.clients[client_id] else current_time
            reset_time = oldest_request + self.window_size
            time_remaining = max(0, reset_time - current_time)
            
            limit_info = {
                "limit": self.max_requests,
                "remaining": 0,
                "reset": reset_time,
                "time_remaining": round(time_remaining, 2)
            }
            
            return False, limit_info
        
        # Добавляем текущий запрос
        self.clients[client_id].append(current_time)
        
        # Вычисляем информацию о лимите для ответа
        limit_info = {
            "limit": self.max_requests,
            "remaining": self.max_requests - current_count - 1,
            "reset": current_time + self.window_size,
            "time_remaining": 0
        }
        
        return True, limit_info
    
    def cleanup(self, max_idle_time: int = 3600):
        """
        Очищает кэш от неактивных клиентов для предотвращения утечки памяти.
        
        Args:
            max_idle_time (int): Максимальное время неактивности клиента в секундах
        """
        current_time = time.time()
        inactive_clients = []
        
        for client_id, timestamps in self.clients.items():
            if not timestamps or current_time - max(timestamps) > max_idle_time:
                inactive_clients.append(client_id)
        
        for client_id in inactive_clients:
            del self.clients[client_id]

class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Middleware для ограничения частоты запросов.
    Использует различные стратегии идентификации клиентов и разные лимиты
    для разных путей API.
    """
    
    def __init__(
        self, 
        app, 
        default_window_size: int = 60,
        default_max_requests: int = 30,
        exclude_paths: List[str] = None,
        path_limits: Dict[str, Tuple[int, int]] = None
    ):
        """
        Инициализирует middleware для ограничения частоты запросов.
        
        Args:
            app: FastAPI приложение
            default_window_size (int): Размер временного окна по умолчанию в секундах
            default_max_requests (int): Максимальное количество запросов по умолчанию
            exclude_paths (List[str], optional): Пути, которые не ограничиваются
            path_limits (Dict[str, Tuple[int, int]], optional): Специальные лимиты для отдельных путей
                в формате {путь: (окно_в_секундах, макс_запросов)}
        """
        super().__init__(app)
        
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/static/"]
        self.default_limiter = RateLimiter(default_window_size, default_max_requests)
        
        # Инициализируем специальные лимитеры для разных путей
        self.path_limiters = {}
        if path_limits:
            for path, (window, max_req) in path_limits.items():
                self.path_limiters[path] = RateLimiter(window, max_req)
    
    async def dispatch(self, request: Request, call_next: Callable):
        """
        Обрабатывает каждый HTTP запрос и проверяет ограничения частоты.
        
        Args:
            request (Request): Объект запроса
            call_next (Callable): Функция для передачи запроса дальше
            
        Returns:
            Response: Ответ от следующего обработчика или ошибка лимита
        """
        # Пропускаем пути, которые не ограничиваются
        for path in self.exclude_paths:
            if request.url.path.startswith(path):
                return await call_next(request)
        
        # Идентификация клиента - по приоритету: пользовательский ID, IP, User-Agent
        client_id = self._get_client_id(request)
        
        # Определяем, какой лимитер использовать
        limiter = self._get_limiter_for_path(request.url.path)
        
        # Проверяем, не превышен ли лимит
        allowed, limit_info = limiter.is_allowed(client_id)
        
        if not allowed:
            # Периодически очищаем неактивных клиентов
            if time.time() % 100 < 1:  # ~1% шанс очистки при каждом запросе
                limiter.cleanup()
            
            logging.warning(f"Превышен лимит запросов для {client_id} на {request.url.path}")
            
            # Возвращаем ошибку с информацией о лимите
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Превышен лимит запросов. Повторите через {limit_info['time_remaining']} секунд."
            )
        
        # Если лимит не превышен, продолжаем обработку запроса
        response = await call_next(request)
        
        # Добавляем заголовки с информацией о лимите
        response.headers["X-RateLimit-Limit"] = str(limit_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(limit_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(int(limit_info["reset"]))
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """
        Определяет идентификатор клиента из данных запроса.
        
        Args:
            request (Request): Объект запроса
            
        Returns:
            str: Идентификатор клиента
        """
        # Пытаемся найти ID пользователя в заголовке Telegram
        header_data = request.headers.get("X-Telegram-Init-Data", "")
        if "user" in header_data and "id" in header_data:
            try:
                # Извлекаем user_id из URL (более надежно, чем парсить заголовок)
                path_parts = request.url.path.split('/')
                for part in path_parts:
                    if part.isdigit():
                        return f"user:{part}"
            except Exception:
                pass
        
        # Если не удалось извлечь ID пользователя, используем IP-адрес
        client_host = request.client.host if request.client else "unknown"
        
        # Если за прокси, пытаемся получить реальный IP из заголовков
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_host = forwarded_for.split(",")[0].strip()
        
        # Добавляем User-Agent для большей точности идентификации
        user_agent = request.headers.get("User-Agent", "")
        user_agent_hash = hash(user_agent) % 10000 if user_agent else ""
        
        return f"ip:{client_host}:{user_agent_hash}"
    
    def _get_limiter_for_path(self, path: str) -> RateLimiter:
        """
        Выбирает подходящий лимитер для указанного пути.
        
        Args:
            path (str): Путь запроса
            
        Returns:
            RateLimiter: Лимитер для указанного пути
        """
        # Проверяем точные совпадения
        if path in self.path_limiters:
            return self.path_limiters[path]
        
        # Проверяем по префиксам
        for prefix, limiter in self.path_limiters.items():
            if path.startswith(prefix):
                return limiter
        
        # Используем лимитер по умолчанию, если не найдено соответствий
        return self.default_limiter 