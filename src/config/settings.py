import os
from dotenv import load_dotenv
import logging
import re
import secrets
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

# Определяем корневую директорию проекта
BASE_DIR = Path(__file__).parent.parent.parent

# Определяем путь к файлу .env
env_path = BASE_DIR / '.env'

# Проверяем существование файла .env
if env_path.exists():
    try:
        # Загрузка переменных окружения из .env файла с поддержкой UTF-8
        load_dotenv(dotenv_path=env_path, encoding='utf-8')
        logging.info(f"Загружены переменные окружения из файла {env_path} (UTF-8)")
    except Exception as e:
        # Если UTF-8 не сработало, пробуем с другой кодировкой
        logging.error(f"Ошибка при загрузке .env с UTF-8: {e}")
        try:
            load_dotenv(dotenv_path=env_path, encoding='cp1251')
            logging.info(f"Загружены переменные окружения из файла {env_path} (CP1251)")
        except Exception as e2:
            logging.error(f"Ошибка при загрузке .env с CP1251: {e2}")
else:
    logging.warning(f"Файл .env не найден по пути {env_path}")

# Настройки логирования
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
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", 8000))

# URL для мини-приложения
WEBAPP_PUBLIC_URL = os.getenv("WEBAPP_PUBLIC_URL", "")

# Настройки базы данных
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/spin_bot")

# Прямая проверка файла .env (без использования уже загруженных переменных)
if env_path.exists():
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            env_content = f.read()
            
        # Ищем строку с WEBAPP_PUBLIC_URL
        webapp_url_match = re.search(r'^WEBAPP_PUBLIC_URL=(.+)$', env_content, re.MULTILINE)
        
        if webapp_url_match:
            # Получаем значение URL из .env напрямую
            env_url = webapp_url_match.group(1).strip()
            
            # Записываем напрямую в переменную окружения
            if env_url and env_url != WEBAPP_PUBLIC_URL:
                logging.warning(f"Обнаружено расхождение: URL из .env файла: {env_url}, а в переменной окружения: {WEBAPP_PUBLIC_URL}")
                
                # Принудительно устанавливаем значение из .env
                os.environ["WEBAPP_PUBLIC_URL"] = env_url
                WEBAPP_PUBLIC_URL = env_url
                logging.info(f"URL установлен в: {WEBAPP_PUBLIC_URL}")
    except Exception as e:
        logging.error(f"Ошибка при прямом чтении URL из .env: {e}")

# Делаем окончательную проверку и очистку URL
if WEBAPP_PUBLIC_URL:
    WEBAPP_PUBLIC_URL = WEBAPP_PUBLIC_URL.strip()
    
    # Проверим, что URL начинается с https://
    if not WEBAPP_PUBLIC_URL.startswith("https://"):
        logging.warning(f"URL не начинается с https://: {WEBAPP_PUBLIC_URL}")
        if WEBAPP_PUBLIC_URL.startswith("http://"):
            https_url = "https://" + WEBAPP_PUBLIC_URL[7:]
            logging.warning(f"URL автоматически преобразован в HTTPS: {https_url}")
            WEBAPP_PUBLIC_URL = https_url
    
    # Экспортируем значение в окружение для гарантии доступности другим модулям
    os.environ["WEBAPP_PUBLIC_URL"] = WEBAPP_PUBLIC_URL
else:
    logging.warning("WEBAPP_PUBLIC_URL не определен в .env файле")

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