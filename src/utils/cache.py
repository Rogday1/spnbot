"""
Кэширование данных для оптимизации производительности приложения.
Используется для хранения часто запрашиваемых данных в памяти, чтобы снизить нагрузку на базу данных.
"""

import time
import logging
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable, TypeVar, Union, List
from collections import defaultdict
from functools import wraps
from src.config import settings

T = TypeVar('T')

class Cache:
    """
    Улучшенный кэш в памяти с поддержкой TTL (time-to-live) и адаптивным TTL для часто запрашиваемых данных.
    Реализует автоматическое очищение устаревших записей и оптимизированную работу с блокировками.
    """
    
    def __init__(self, default_ttl: int = 60):
        """
        Инициализирует кэш с заданным временем жизни записей по умолчанию.
        
        Args:
            default_ttl (int): Время жизни записей в секундах по умолчанию
        """
        self.default_ttl = default_ttl
        self.data: Dict[str, Dict[str, Any]] = {}
        self.expiry: Dict[str, float] = {}
        self.access_count: Dict[str, int] = {}  # Счетчик обращений к каждому ключу
        self.last_access: Dict[str, float] = {}  # Время последнего обращения
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "cleanups": 0,
            "errors": 0
        }
        self.locks = defaultdict(asyncio.Lock)
        
        # Загружаем настройки TTL из конфигурации
        self.ttl_settings = getattr(settings, 'CACHE_TTL', {})
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Получает значение из кэша, если оно существует и не устарело.
        Обновляет статистику обращений для адаптивного TTL.
        
        Args:
            key (str): Ключ для поиска в кэше
            
        Returns:
            Optional[Any]: Значение из кэша или None, если ключ не найден или устарел
        """
        try:
            # Проверяем, есть ли ключ в кэше и не истек ли его срок действия
            if key in self.data and key in self.expiry:
                if time.time() < self.expiry[key]:
                    # Обновляем статистику обращений
                    self.access_count[key] = self.access_count.get(key, 0) + 1
                    self.last_access[key] = time.time()
                    
                    self.stats["hits"] += 1
                    return self.data[key]
                else:
                    # Если срок действия истек, удаляем запись
                    await self.delete(key)
            
            self.stats["misses"] += 1
            return None
            
        except Exception as e:
            logging.error(f"Ошибка при получении данных из кэша для ключа {key}: {e}")
            self.stats["errors"] += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Устанавливает значение в кэш с указанным временем жизни.
        Если TTL не указан, определяет его на основе типа данных или дефолтного значения.
        
        Args:
            key (str): Ключ для сохранения в кэше
            value (Any): Значение для сохранения
            ttl (Optional[int]): Время жизни в секундах или None для значения, определяемого типом данных
        """
        try:
            # Определяем TTL на основе типа данных из ключа или дефолтного значения
            if ttl is None:
                # Проверяем, есть ли специфический TTL для этого типа данных
                for data_type, specific_ttl in self.ttl_settings.items():
                    if data_type in key:
                        ttl = specific_ttl
                        break
                
                # Если не найден специфический TTL, используем значение по умолчанию
                if ttl is None:
                    ttl = self.default_ttl
            
            # Применяем адаптивный TTL для часто запрашиваемых данных
            if key in self.access_count and self.access_count[key] > 10:
                # Для часто запрашиваемых данных увеличиваем TTL до 2х от указанного
                ttl = min(ttl * 2, 3600)  # Но не более часа
            
            # Вычисляем время истечения срока действия
            expiry_time = time.time() + ttl
            
            # Сохраняем данные и время истечения
            self.data[key] = value
            self.expiry[key] = expiry_time
            self.access_count[key] = self.access_count.get(key, 0)
            self.last_access[key] = time.time()
            
            self.stats["sets"] += 1
            
        except Exception as e:
            logging.error(f"Ошибка при установке данных в кэш для ключа {key}: {e}")
            self.stats["errors"] += 1
    
    async def delete(self, key: str) -> bool:
        """
        Удаляет запись из кэша.
        
        Args:
            key (str): Ключ для удаления
            
        Returns:
            bool: True, если ключ был в кэше и успешно удален, иначе False
        """
        try:
            if key in self.data:
                del self.data[key]
                if key in self.expiry:
                    del self.expiry[key]
                if key in self.access_count:
                    del self.access_count[key]
                if key in self.last_access:
                    del self.last_access[key]
                
                self.stats["deletes"] += 1
                return True
            return False
            
        except Exception as e:
            logging.error(f"Ошибка при удалении данных из кэша для ключа {key}: {e}")
            self.stats["errors"] += 1
            return False
    
    async def delete_by_pattern(self, pattern: str) -> int:
        """
        Удаляет все записи, ключи которых содержат указанный паттерн.
        
        Args:
            pattern (str): Строка для поиска в ключах
            
        Returns:
            int: Количество удаленных записей
        """
        try:
            keys_to_delete = [key for key in self.data.keys() if pattern in key]
            
            for key in keys_to_delete:
                await self.delete(key)
            
            return len(keys_to_delete)
            
        except Exception as e:
            logging.error(f"Ошибка при удалении данных из кэша по паттерну {pattern}: {e}")
            self.stats["errors"] += 1
            return 0
    
    async def clear(self) -> None:
        """Очищает весь кэш."""
        try:
            self.data.clear()
            self.expiry.clear()
            self.access_count.clear()
            self.last_access.clear()
            
        except Exception as e:
            logging.error(f"Ошибка при очистке кэша: {e}")
            self.stats["errors"] += 1
    
    async def cleanup(self) -> int:
        """
        Удаляет все устаревшие записи из кэша.
        Также удаляет редко используемые записи для оптимизации памяти.
        
        Returns:
            int: Количество удаленных записей
        """
        try:
            current_time = time.time()
            
            # Удаляем просроченные записи
            expired_keys = [key for key, expiry in self.expiry.items() if current_time > expiry]
            
            # Также удаляем записи, к которым не обращались более 1 часа и они были запрошены менее 3 раз
            # (оптимизация памяти для редко используемых данных)
            unused_keys = [
                key for key in self.last_access.keys() 
                if current_time - self.last_access.get(key, 0) > 3600  # Более часа не обращались
                and self.access_count.get(key, 0) < 3  # И менее 3 обращений
            ]
            
            # Объединяем списки ключей для удаления
            keys_to_delete = list(set(expired_keys + unused_keys))
            
            for key in keys_to_delete:
                await self.delete(key)
            
            if keys_to_delete:
                self.stats["cleanups"] += 1
                logging.debug(f"Очищено {len(keys_to_delete)} записей из кэша ({len(expired_keys)} просроченных, {len(unused_keys)} неиспользуемых)")
            
            return len(keys_to_delete)
            
        except Exception as e:
            logging.error(f"Ошибка при очистке устаревших записей: {e}")
            self.stats["errors"] += 1
            return 0
    
    async def get_or_compute(
        self, 
        key: str, 
        compute_func: Callable[[], Awaitable[T]], 
        ttl: Optional[int] = None
    ) -> T:
        """
        Возвращает значение из кэша или вычисляет и кэширует его, если оно отсутствует.
        
        Args:
            key (str): Ключ для кэша
            compute_func (Callable[[], Awaitable[T]]): Асинхронная функция для вычисления значения
            ttl (Optional[int]): Время жизни кэша в секундах
            
        Returns:
            T: Значение из кэша или результат вычисления
        """
        try:
            # Сначала пытаемся получить значение из кэша
            value = await self.get(key)
            
            # Если значение найдено, возвращаем его
            if value is not None:
                return value
            
            # Получаем блокировку для ключа, чтобы избежать "гонки вычислений"
            async with self.locks[key]:
                # Повторно проверяем, не появилось ли значение в кэше
                # пока мы ждали получения блокировки
                value = await self.get(key)
                if value is not None:
                    return value
                
                # Вычисляем значение
                try:
                    value = await compute_func()
                except Exception as e:
                    logging.error(f"Ошибка при вычислении значения для ключа {key}: {e}")
                    self.stats["errors"] += 1
                    raise
                
                # Кэшируем его
                await self.set(key, value, ttl)
                
                return value
                
        except Exception as e:
            logging.error(f"Ошибка при получении/вычислении значения для ключа {key}: {e}")
            self.stats["errors"] += 1
            # Пробуем вычислить значение без кэширования в случае ошибки
            return await compute_func()
    
    def get_stats(self) -> Dict[str, Union[int, float]]:
        """
        Возвращает подробную статистику использования кэша.
        
        Returns:
            Dict[str, Union[int, float]]: Словарь со статистикой
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        # Собираем статистику использования ключей
        frequent_keys = []
        if self.access_count:
            top_keys = sorted(self.access_count.items(), key=lambda x: x[1], reverse=True)[:5]
            frequent_keys = [{"key": k, "count": v} for k, v in top_keys]
        
        # Вычисляем среднее время жизни кэша
        avg_ttl = 0
        if self.expiry:
            current_time = time.time()
            remaining_ttls = [expiry - current_time for expiry in self.expiry.values() if expiry > current_time]
            if remaining_ttls:
                avg_ttl = sum(remaining_ttls) / len(remaining_ttls)
        
        return {
            **self.stats,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "items_count": len(self.data),
            "avg_ttl": avg_ttl,
            "frequent_keys": frequent_keys
        }

# Глобальный экземпляр кэша
cache = Cache(default_ttl=60)

def cached(ttl: Optional[int] = None, key_prefix: str = None):
    """
    Декоратор для кэширования результатов асинхронных функций.
    
    Args:
        ttl (Optional[int]): Время жизни кэша в секундах
        key_prefix (str): Префикс для ключа кэша, позволяет группировать кэши по типам данных
        
    Returns:
        Callable: Декорированная функция
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Формируем ключ кэша из имени функции, префикса и аргументов
            prefix = key_prefix or func.__name__
            key_parts = [prefix]
            
            # Добавляем только значимые аргументы, исключая self и объекты сессий
            valid_args = []
            for arg in args:
                # Пропускаем self и объекты сессий, которые не должны влиять на ключ кэша
                arg_str = str(arg)
                if not arg_str.startswith("<") or not arg_str.endswith(">"):
                    valid_args.append(arg_str)
            
            key_parts.extend(valid_args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
            
            # Используем встроенный механизм get_or_compute для получения значения
            try:
                return await cache.get_or_compute(
                    cache_key,
                    lambda: func(*args, **kwargs),
                    ttl
                )
            except Exception as e:
                logging.error(f"Ошибка при исполнении кэшированной функции {func.__name__}: {e}")
                # В случае ошибки кэширования, просто вызываем функцию напрямую
                return await func(*args, **kwargs)
        return wrapper
    return decorator

async def start_cache_cleanup_task():
    """
    Запускает фоновую задачу для периодической очистки устаревших записей кэша.
    Обрабатывает сигналы отмены для корректного завершения работы.
    """
    try:
        logging.info("Запущена задача очистки кэша")
        while True:
            try:
                removed = await cache.cleanup()
                if removed > 0:
                    logging.debug(f"Очищено {removed} устаревших записей из кэша")
            except Exception as e:
                logging.error(f"Ошибка при очистке кэша: {e}")
            
            # Спим между очистками с возможностью прерывания
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                logging.info("Задача очистки кэша получила сигнал отмены, завершаем корректно")
                break
                
    except asyncio.CancelledError:
        # Корректно обрабатываем отмену задачи
        logging.info("Задача очистки кэша отменена, завершаем работу")
    except Exception as e:
        logging.error(f"Необработанное исключение в задаче очистки кэша: {e}")
        # Не перезапускаем задачу автоматически, чтобы избежать цикла ошибок
        # В случае необходимости перезапуск должен выполнить вызывающий код
    finally:
        logging.info("Задача очистки кэша завершена") 