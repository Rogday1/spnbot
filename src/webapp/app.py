from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from aiogram import Bot
import logging
import uvicorn
from pathlib import Path
import asyncio

from src.config import settings
from src.webapp.routers import user_router, game_router, leaders_router
from src.webapp.middlewares import TelegramAuthMiddleware, RateLimiterMiddleware, SubscriptionCheckMiddleware

# Получаем абсолютный путь до директории со статическими файлами
STATIC_DIR = Path(__file__).parent / "static"

def setup_webapp(bot: Bot) -> FastAPI:
    """
    Настройка FastAPI приложения.
    
    Args:
        bot (Bot): Экземпляр бота Telegram
        
    Returns:
        FastAPI: Настроенное FastAPI приложение
    """
    app = FastAPI(
        title="Spin Bot Web App",
        description="API для взаимодействия с мини-приложением Telegram бота",
        version="2.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )
    
    # Добавляем middleware для безопасности и оптимизации
    
    # 1. CORS middleware для разрешения запросов с определенных источников
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )
    
    # 2. Сжатие ответов для экономии трафика
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # 3. Проверка источников запросов
    if not settings.DEBUG:
        allowed_hosts = [settings.WEBAPP_HOST]
        if settings.WEBAPP_PUBLIC_URL:
            try:
                from urllib.parse import urlparse
                parsed_url = urlparse(settings.WEBAPP_PUBLIC_URL)
                if parsed_url.netloc:
                    allowed_hosts.append(parsed_url.netloc)
            except Exception as e:
                logging.warning(f"Ошибка при парсинге WEBAPP_PUBLIC_URL: {e}")
        
        app.add_middleware(
            TrustedHostMiddleware, 
            allowed_hosts=allowed_hosts + ["telegram.org", "t.me"]
        )
    
    # 4. Ограничение частоты запросов для защиты от DDoS
    app.add_middleware(
        RateLimiterMiddleware,
        default_window_size=settings.RATE_LIMIT_DEFAULT["window_size"],
        default_max_requests=settings.RATE_LIMIT_DEFAULT["max_requests"],
        path_limits=settings.RATE_LIMIT_PATHS
    )
    
    # 5. Проверка аутентификации Telegram WebApp
    app.add_middleware(
        TelegramAuthMiddleware,
        bot_token=settings.BOT_TOKEN,
        exclude_paths=["/docs", "/redoc", "/openapi.json", "/", "/game", "/api/user/check_subscription", "/favicon.ico"],
        exclude_prefixes=["/static/"]
    )
    
    # 6. Проверка подписки на обязательные каналы
    app.add_middleware(
        SubscriptionCheckMiddleware,
        bot_instance=bot,
        api_path_prefix="/api/spin/",
        exclude_paths=["/docs", "/redoc", "/openapi.json", "/"],
        exclude_prefixes=["/static/"]
    )
    
    # Добавляем бота в состояние приложения
    app.state.bot = bot
    
    # Подключаем статические файлы
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    
    # Подключаем роутеры
    app.include_router(user_router)
    app.include_router(game_router)
    app.include_router(leaders_router)
    
    # Настройка корневого пути
    @app.get("/")
    async def root():
        return {"message": "Spin Bot Web API is running", "version": "2.0.0"}
    
    logging.info(f"Веб-приложение настроено, статические файлы будут доступны из {STATIC_DIR}")
    
    return app

async def start_webapp(app: FastAPI, shutdown_event=None) -> None:
    """
    Запуск веб-сервера с приложением FastAPI.
    
    Args:
        app (FastAPI): Экземпляр FastAPI приложения
        shutdown_event (asyncio.Event, optional): Событие для сигнализации остановки сервера
    """
    # Настройка конфигурации uvicorn для продакшн или dev среды
    config = uvicorn.Config(
        app=app,
        host=settings.WEBAPP_HOST,
        port=settings.WEBAPP_PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else 4,  # Больше воркеров для продакшн
        log_level="info" if settings.DEBUG else "warning",
        access_log=settings.DEBUG,  # Отключаем логи доступа в продакшн
        proxy_headers=True,  # Доверяем заголовкам прокси
        forwarded_allow_ips="*"  # Разрешаем все IP для заголовков X-Forwarded-*
    )
    server = uvicorn.Server(config)
    
    if shutdown_event:
        # Создаем задачу для запуска сервера
        server_task = asyncio.create_task(server.serve())
        logging.info(f"Веб-сервер запущен на {settings.WEBAPP_HOST}:{settings.WEBAPP_PORT} с поддержкой shutdown_event")
        
        # Создаем задачу для ожидания события завершения
        shutdown_task = asyncio.create_task(shutdown_event.wait(), name="webapp_shutdown_task")
        
        # Ждем либо завершения сервера, либо сигнала завершения
        done, pending = await asyncio.wait(
            [server_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Если сервер завершился сам, просто логируем это
        if server_task in done:
            try:
                result = server_task.result()
                logging.info(f"Веб-сервер завершил работу: {result}")
            except Exception as e:
                logging.error(f"Веб-сервер завершился с ошибкой: {e}")
        else:
            # Если получен сигнал завершения, останавливаем сервер
            logging.info("Получен сигнал завершения работы, останавливаем веб-сервер")
            # Отменяем задачу сервера
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                logging.info("Веб-сервер остановлен")
            except Exception as e:
                logging.error(f"Ошибка при остановке веб-сервера: {e}")
    else:
        # Обычный запуск без поддержки события остановки
        logging.info(f"Веб-сервер запускается на {settings.WEBAPP_HOST}:{settings.WEBAPP_PORT}")
        await server.serve()
    
    logging.info(f"Веб-сервер завершил работу")
