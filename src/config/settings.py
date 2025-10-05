import os
import re
import secrets
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

def create_env_file():
    """Создает .env файл из переменных окружения Railway"""
    env_content = []
    
    # Основные переменные
    bot_token = os.getenv('BOT_TOKEN')
    if bot_token:
        # Убираем лишние кавычки, пробелы и символы
        bot_token = bot_token.strip().strip('"').strip("'").strip('=').strip()
        if bot_token:
            env_content.append(f'BOT_TOKEN={bot_token}')
    
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        # Убираем лишние кавычки и пробелы
        database_url = database_url.strip().strip('"').strip("'").strip(';').strip()
        # Заменяем ssl=true на sslmode=require для совместимости
        if '?ssl=true' in database_url:
            database_url = database_url.replace('?ssl=true', '?sslmode=require')
        env_content.append(f'DATABASE_URL={database_url}')
    
    debug = os.getenv('DEBUG')
    if debug:
        debug = debug.strip().strip('"').strip("'").strip(';').strip()
        env_content.append(f'DEBUG={debug}')
    
    webapp_url = os.getenv('WEBAPP_PUBLIC_URL')
    if webapp_url:
        webapp_url = webapp_url.strip().strip('"').strip("'").strip(';').strip()
        env_content.append(f'WEBAPP_PUBLIC_URL={webapp_url}')
    
    # Записываем в .env файл
    if env_content:
        env_path = Path('.env')
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(env_content))
        print(f"Создан .env файл с {len(env_content)} переменными")
        print("Содержимое .env файла:")
        for line in env_content:
            print(f"  {line}")
        
        # Загружаем переменные из .env файла в окружение
        from dotenv import load_dotenv
        load_dotenv(env_path, override=True)
        print("Переменные загружены из .env файла")

# Создаем .env файл и загружаем переменные
create_env_file()

# Загружаем .env файл если он существует
env_path = Path('.env')
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path, override=True)
    print("Загружен .env файл")

# Отладочная информация
print("=== Отладочная информация ===")
print(f"BOT_TOKEN из окружения: '{os.getenv('BOT_TOKEN')}'")
print(f"DATABASE_URL из окружения: '{os.getenv('DATABASE_URL')}'")
print(f"DEBUG из окружения: '{os.getenv('DEBUG')}'")
print(f"WEBAPP_PUBLIC_URL из окружения: '{os.getenv('WEBAPP_PUBLIC_URL')}'")
print("============================")

# Определяем корневую директорию проекта
BASE_DIR = Path(__file__).parent.parent.parent

# Определяем путь к файлу .env
env_path = BASE_DIR / '.env'

# Настройки логирования - ПЕРЕМЕЩЕНО ПОСЛЕ загрузки переменных окружения
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(), # Вывод в консоль
        logging.FileHandler(LOG_FILE) if LOG_FILE else logging.NullHandler() # Вывод в файл, если указан
    ]
)

# Устанавливаем уровень логирования для корневого логгера
logging.getLogger().setLevel(LOG_LEVEL)

# Основные настройки
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

# Настройки бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Настройки вебхука
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook/bot/")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else None

# Настройки веб-приложения
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", 8001))

# URL для мини-приложения
WEBAPP_PUBLIC_URL = os.getenv("WEBAPP_PUBLIC_URL", "http://localhost:8001")

def reload_settings():
    """Принудительно перезагружает настройки из .env файла"""
    global WEBAPP_PUBLIC_URL, BOT_TOKEN, DATABASE_URL, DEBUG
    
    # Загружаем .env файл заново
    env_path = Path('.env')
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path, override=True)
        print("🔄 Настройки перезагружены из .env файла")
    
    # Обновляем переменные
    WEBAPP_PUBLIC_URL = os.getenv("WEBAPP_PUBLIC_URL", "http://localhost:8001")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/spin_bot")
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
    
    print(f"✅ WEBAPP_PUBLIC_URL обновлен: {WEBAPP_PUBLIC_URL}")
    return WEBAPP_PUBLIC_URL

# Настройки базы данных
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/spin_bot")

# Настройки безопасности
# Генерируем случайный ключ для сессий и подписей, если его нет в переменных окружения
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    logging.warning("SECRET_KEY не был найден в переменных окружения. Сгенерирован временный ключ.")

# Настройки для CORS
CORS_ORIGINS = [
    "https://telegram.org",
    "https://t.me",
    "https://tgspin.ru",  # Добавляем домен tgspin.ru
]

# Если задан WEBAPP_PUBLIC_URL, добавляем его в список разрешенных источников
if WEBAPP_PUBLIC_URL:
    CORS_ORIGINS.append(WEBAPP_PUBLIC_URL)

# В режиме отладки разрешаем все источники
if DEBUG:
    CORS_ORIGINS = ["*"]

# Настройки для Rate Limiting (ограничение частоты запросов)
RATE_LIMIT_DEFAULT = {
    "window_size": 60,  # 60 секунд
    "max_requests": 30  # 30 запросов в минуту
}

RATE_LIMIT_PATHS = {
    "/api/spin/": (10, 5),  # 5 запросов в 10 секунд для прокрутки колеса
    "/api/user/": (60, 30),  # 30 запросов в минуту для пользовательских данных
}

# Настройки сессий
SESSION_COOKIE_NAME = "spinbot_session"
SESSION_COOKIE_SECURE = not DEBUG  # В production используем только HTTPS
SESSION_COOKIE_HTTPONLY = True  # Запрещаем доступ к куки из JavaScript
SESSION_COOKIE_SAMESITE = "Lax"  # Ограничение отправки куки при переходе с других сайтов

# Настройки кэширования
CACHE_TTL = {
    "user": 60,           # 1 минута для данных пользователя
    "leaders": 300,       # 5 минут для лидерборда
    "game_history": 600,  # 10 минут для истории игр
}

# Настройки игры
FREE_SPIN_INTERVAL = int(os.getenv("FREE_SPIN_INTERVAL", "86400"))  # 24 часа между бесплатными прокрутками
INITIAL_TICKETS = int(os.getenv("INITIAL_TICKETS", "1"))  # Начальное количество билетов для новых пользователей
MAX_WIN_PER_DAY = int(os.getenv("MAX_WIN_PER_DAY", "5000"))  # Максимальный выигрыш за день (для всех пользователей)

# Обязательные каналы для подписки
REQUIRED_CHANNELS = []
required_channels_str = os.getenv("REQUIRED_CHANNELS", "")
if required_channels_str:
    # Разбиваем строку с каналами по запятой и удаляем пробелы
    REQUIRED_CHANNELS = [channel.strip() for channel in required_channels_str.split(',') if channel.strip()]
    if DEBUG:
        logging.info(f"Загружены обязательные каналы для подписки: {REQUIRED_CHANNELS}")

# Проверка обязательных переменных окружения
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения")

# Отладочная информация
if DEBUG:
    logging.info(f"Конфигурация загружена. Режим отладки: {DEBUG}")
    logging.info(f"URL для WebApp: {WEBAPP_PUBLIC_URL if WEBAPP_PUBLIC_URL else 'не задан'}")
    logging.info(f"Веб-сервер на {WEBAPP_HOST}:{WEBAPP_PORT}")
    logging.info(f"База данных: {DATABASE_URL}")
    logging.info(f"Максимальный выигрыш за день: {MAX_WIN_PER_DAY}")

# Проверка наличия критически важных настроек
if not BOT_TOKEN and not DEBUG:
    logging.warning("BOT_TOKEN не установлен! Аутентификация Telegram WebApp работать не будет.")

if not WEBAPP_PUBLIC_URL and not DEBUG:
    logging.warning("WEBAPP_PUBLIC_URL не установлен! Это может привести к проблемам с мини-приложением.")

# Для отладки: вывод текущих настроек
if DEBUG:
    logging.info("Загруженные настройки:")
    logging.info(f"DEBUG: {DEBUG}")
    logging.info(f"WEBAPP_HOST: {WEBAPP_HOST}")
    logging.info(f"WEBAPP_PORT: {WEBAPP_PORT}")
    logging.info(f"WEBAPP_PUBLIC_URL: {WEBAPP_PUBLIC_URL}")
    logging.info(f"DATABASE_URL: {DATABASE_URL}")
    logging.info(f"CORS_ORIGINS: {CORS_ORIGINS}")