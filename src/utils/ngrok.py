import logging
from src.config import settings
import os
import re

def get_game_url(base_url=None):
    """
    Возвращает URL для мини-приложения игры.
    
    Args:
        base_url (str, optional): Базовый URL. 
            Если None, используется URL из настроек.
            
    Returns:
        str: Полный URL для мини-приложения
    """
    # ВАЖНО: Непосредственно читаем значение из переменной окружения,
    # чтобы избежать проблем с кешированием значений
    env_url = os.environ.get('WEBAPP_PUBLIC_URL')
    
    # Используем переданный URL, если он есть
    if base_url:
        base_url = base_url.strip().rstrip('/')
        logging.info(f"Использую переданный URL: {base_url}")
        result = f"{base_url}/game"
        logging.info(f"Итоговый URL (из переданного): {result}")
        return result
    
    # Если URL есть в переменной окружения, используем его
    if env_url and env_url.strip():
        base_url = env_url.strip().rstrip('/')
        
        # URL из .env имеет приоритет над settings.WEBAPP_PUBLIC_URL
        logging.info(f"Использую URL из переменной окружения: {base_url}")
        
        if base_url == "https://your-tunnel-url-here.com":
            logging.error("⚠️ URL в .env файле не был заменен на реальный URL!")
            # Возвращаем заведомо неправильный URL, чтобы увидеть ошибку и исправить
            return "https://ERROR-REPLACE-URL-IN-ENV-FILE"
        
        result = f"{base_url}/game"
        logging.info(f"Итоговый URL (из переменной окружения): {result}")
        return result
        
    # Если нет в окружении, но есть в settings, используем его
    if settings.WEBAPP_PUBLIC_URL and settings.WEBAPP_PUBLIC_URL.strip():
        base_url = settings.WEBAPP_PUBLIC_URL.strip().rstrip('/')
        logging.info(f"Использую URL из settings: {base_url}")
        
        result = f"{base_url}/game"
        logging.info(f"Итоговый URL (из settings): {result}")
        return result
    
    # Если нигде нет URL, возвращаем ошибку
    logging.error("❌ URL для WebApp не найден! Проверьте файл .env")
    return "https://ERROR-NO-URL-CONFIGURED" 