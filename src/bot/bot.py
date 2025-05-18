from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import logging
import traceback
import asyncio

from src.config import settings

async def setup_bot() -> tuple[Bot, Dispatcher]:
    """
    Настройка и инициализация бота и диспетчера.
    
    Returns:
        tuple[Bot, Dispatcher]: Настроенные экземпляры бота и диспетчера
    """
    try:
        # Создаем бота с настройками
        logging.info("Создание экземпляра бота...")
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=None)  # Отключаем Markdown по умолчанию
        )
        
        # Создаем диспетчер
        logging.info("Создание диспетчера...")
        dp = Dispatcher()
        
        # Регистрация обработчиков
        logging.info("Регистрация обработчиков...")
        from .handlers import register_all_handlers
        register_all_handlers(dp)
        
        # Регистрация middleware
        from .middlewares import setup_middlewares
        setup_middlewares(dp)
        
        logging.info("Бот настроен и готов к запуску")
        
        return bot, dp
    except Exception as e:
        logging.error(f"Ошибка при настройке бота: {e}")
        logging.error(traceback.format_exc())
        raise

async def start_polling(bot: Bot, dp: Dispatcher, shutdown_event=None) -> None:
    """
    Запуск бота в режиме long polling.
    
    Args:
        bot (Bot): Экземпляр бота
        dp (Dispatcher): Экземпляр диспетчера
        shutdown_event (asyncio.Event, optional): Событие для сигнализации остановки бота
    """
    try:
        logging.info("Запуск бота в режиме long polling")
        
        # Запускаем бота в режиме поллинга
        if shutdown_event:
            # С поддержкой события завершения
            logging.info("Запуск с поддержкой события завершения работы")
            polling_task = asyncio.create_task(
                dp.start_polling(
                    bot, 
                    allowed_updates=dp.resolve_used_update_types(),
                    skip_updates=True  # Пропускаем старые обновления при запуске
                ),
                name="bot_polling_task"
            )
            logging.info(f"Задача поллинга создана и запущена")
            
            # Создаем отдельную задачу для ожидания события shutdown
            shutdown_task = asyncio.create_task(shutdown_event.wait(), name="shutdown_wait_task")
            
            # Передаем две задачи в asyncio.wait()
            done, pending = await asyncio.wait(
                [polling_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Если поллинг завершился сам, просто выходим
            if polling_task in done:
                result = polling_task.result()
                logging.info(f"Поллинг завершился: {result}")
            else:
                # Иначе отменяем задачу поллинга
                logging.info("Получен сигнал завершения работы, останавливаем поллинг")
                polling_task.cancel()
                try:
                    await polling_task
                except asyncio.CancelledError:
                    logging.info("Поллинг остановлен")
        else:
            # Обычный запуск без поддержки события остановки
            await dp.start_polling(
                bot, 
                allowed_updates=dp.resolve_used_update_types(),
                skip_updates=True  # Пропускаем старые обновления при запуске
            )
    except Exception as e:
        logging.error(f"Ошибка при запуске поллинга: {e}")
        logging.error(traceback.format_exc())
        raise

async def setup_webhook(bot: Bot, dp: Dispatcher) -> None:
    """
    Настройка вебхука для бота.
    
    Args:
        bot (Bot): Экземпляр бота
        dp (Dispatcher): Экземпляр диспетчера
    """
    webhook_info = await bot.get_webhook_info()
    
    if webhook_info.url != settings.WEBHOOK_URL:
        if webhook_info.url:
            await bot.delete_webhook()
        
        await bot.set_webhook(
            url=settings.WEBHOOK_URL,
            allowed_updates=dp.resolve_used_update_types()
        )
        logging.info(f"Вебхук настроен на URL: {settings.WEBHOOK_URL}")
    else:
        logging.info(f"Вебхук уже настроен на URL: {settings.WEBHOOK_URL}")
