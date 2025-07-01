import asyncio
import logging
import sys
import argparse
import signal
import functools
from src.config import settings
from src.bot.bot import setup_bot, start_polling
from src.webapp.app import setup_webapp, start_webapp
from src.database.db import init_db
from src.utils.cache import start_cache_cleanup_task
from src.utils.daily_reset_task import schedule_daily_reset
from src.database.repositories import UserRepository
#хай
#gggg
# Глобальные переменные для хранения задач
background_tasks = []
shutdown_event = asyncio.Event()

# Обработчик сигналов для корректного завершения работы
def handle_shutdown_signal(sig, loop):
    """Обработчик сигналов для корректного завершения работы приложения."""
    logging.info(f"Получен сигнал завершения: {sig}")
    shutdown_event.set()
    # Отменяем все задачи (кроме текущей)
    for task in asyncio.all_tasks(loop=loop):
        if task is not asyncio.current_task(loop=loop):
            task.cancel()

async def main():
    """Точка входа в приложение."""
    # Настройка обработчиков сигналов
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig, 
                    functools.partial(handle_shutdown_signal, sig, loop)
                )
                logging.info(f"Зарегистрирован обработчик сигнала {sig}")
            except NotImplementedError:
                # Для систем, где add_signal_handler не поддерживается (Windows)
                logging.info(f"Обработчик сигнала {sig} не зарегистрирован - не поддерживается платформой")
    except Exception as e:
        logging.warning(f"Не удалось настроить обработчики сигналов: {e}")
        # Продолжаем работу без обработчиков сигналов
    
    # Разбор аргументов командной строки
    parser = argparse.ArgumentParser(description="Запуск Spin Bot v2.0")
    parser.add_argument("--url", help="HTTPS URL для WebApp (переопределяет настройку WEBAPP_PUBLIC_URL в .env)")
    parser.add_argument("--cleanup", action="store_true", help="Запустить очистку дубликатов пользователей")
    args = parser.parse_args()
    
    # Если указан URL в аргументах, переопределяем настройку
    if args.url:
        settings.WEBAPP_PUBLIC_URL = args.url
        logging.info(f"WEBAPP_PUBLIC_URL переопределен из аргументов командной строки: {args.url}")
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO if settings.DEBUG else logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    logging.info("Запуск Spin Bot v2.0")
    
    try:
        # Инициализация базы данных
        logging.info("Инициализация базы данных...")
        db_session = await init_db()
        # Если указан флаг --cleanup, запускаем очистку дубликатов и завершаем работу
        if args.cleanup:
            logging.info("Запуск очистки дубликатов пользователей...")
            user_repo = UserRepository(db_session)
            removed = await user_repo.check_and_clean_duplicates()
            logging.info(f"Очистка завершена. Удалено дубликатов: {removed}")
            return
        
        # Настраиваем бота
        logging.info("Настройка бота...")
        bot, dp = await setup_bot()
        
        # Настраиваем веб-приложение
        logging.info("Настройка веб-приложения...")
        app = setup_webapp(bot)
        
        # Выводим используемый URL
        logging.info(f"URL для WebApp: {settings.WEBAPP_PUBLIC_URL}")
        
        # Запускаем задачу очистки кэша с обработкой исключений и повторными попытками
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                cache_cleanup_task = asyncio.create_task(
                    start_cache_cleanup_task(),
                    name="cache_cleanup_task"
                )
                background_tasks.append(cache_cleanup_task)
                logging.info("Запущена фоновая задача очистки кэша")
                
                # Устанавливаем обработчик завершения задачи
                cache_cleanup_task.add_done_callback(
                    lambda t: logging.error(f"Задача очистки кэша завершилась с ошибкой: {t.exception()}") if t.exception() else None
                )
                break
            except Exception as e:
                retry_count += 1
                logging.error(f"Ошибка при запуске задачи очистки кэша (попытка {retry_count}/{max_retries}): {e}")
                if retry_count >= max_retries:
                    logging.warning("Приложение продолжит работу без очистки кэша после максимального числа попыток")
                else:
                    await asyncio.sleep(1)  # Пауза перед повторной попыткой
        
        # Запускаем задачу ежедневного сброса статистики
        try:
            daily_reset_task = asyncio.create_task(
                schedule_daily_reset(),
                name="daily_reset_task"
            )
            background_tasks.append(daily_reset_task)
            logging.info("Запущена задача ежедневного сброса статистики")
            
            # Устанавливаем обработчик завершения задачи
            daily_reset_task.add_done_callback(
                lambda t: logging.error(f"Задача ежедневного сброса завершилась с ошибкой: {t.exception()}") if t.exception() else None
            )
        except Exception as e:
            logging.error(f"Ошибка при запуске задачи ежедневного сброса статистики: {e}")
            logging.warning("Приложение продолжит работу без ежедневного сброса статистики")
        
        # Запускаем бота и веб-приложение
        logging.info("Запуск бота и веб-приложения...")
        
        # Запускаем веб-приложение в отдельной задаче
        logging.info("Запуск веб-приложения...")
        try:
            webapp_task = asyncio.create_task(start_webapp(app, shutdown_event=shutdown_event), name="webapp_task")
            background_tasks.append(webapp_task)
            
            # Устанавливаем обработчик завершения задачи
            webapp_task.add_done_callback(
                lambda t: logging.error(f"Задача веб-приложения завершилась с ошибкой: {t.exception()}") if t.exception() else None
            )
        except TypeError as e:
            # Обработка случая, если версия start_webapp не поддерживает shutdown_event
            if "shutdown_event" in str(e):
                logging.warning("Версия start_webapp не поддерживает shutdown_event, запуск в обычном режиме")
                webapp_task = asyncio.create_task(start_webapp(app), name="webapp_task")
                background_tasks.append(webapp_task)
            else:
                raise
        
        # Запускаем бота в режиме поллинга с проверкой флага завершения
        logging.info("Бот запускается в режиме long polling")
        try:
            # Запускаем бота и ждем завершения работы или сигнала остановки
            await start_polling(bot, dp, shutdown_event=shutdown_event)
            logging.info("Бот завершил работу")
        except TypeError as e:
            # Обработка случая, если версия start_polling не поддерживает shutdown_event
            if "shutdown_event" in str(e):
                logging.warning("Версия start_polling не поддерживает shutdown_event, запуск в обычном режиме")
                await start_polling(bot, dp)
                logging.info("Бот завершил работу")
            else:
                logging.error(f"Ошибка при запуске бота: {e}")
                raise
        
        # Ждем сигнала завершения, если бот завершился штатно и сигнал еще не установлен
        if not shutdown_event.is_set():
            logging.info("Ожидание сигнала завершения работы...")
            await shutdown_event.wait()
        
        # Корректное завершение работы
        logging.info("Начинаем корректное завершение работы всех компонентов...")
        await shutdown()
        
    except Exception as e:
        logging.error(f"Ошибка при запуске: {e}")
        # В случае фатальной ошибки при запуске, пытаемся корректно завершить работу
        try:
            await shutdown()
        except Exception as shutdown_err:
            logging.error(f"Ошибка при завершении работы после критической ошибки: {shutdown_err}")
        
        raise

async def shutdown():
    """Корректное завершение работы приложения."""
    logging.info("Завершение работы приложения...")
    
    # Отменяем все фоновые задачи
    for task in background_tasks:
        if task and not task.done():
            logging.debug(f"Отмена задачи: {task.get_name() if hasattr(task, 'get_name') else 'unnamed'}")
            task.cancel()
            try:
                # Устанавливаем тайм-аут для ожидания отмены задачи
                await asyncio.wait_for(task, timeout=5.0)
                logging.debug(f"Задача успешно отменена")
            except asyncio.TimeoutError:
                logging.warning(f"Тайм-аут при отмене задачи")
            except asyncio.CancelledError:
                logging.debug(f"Задача успешно отменена")
            except Exception as e:
                logging.error(f"Ошибка при отмене задачи: {e}")
    
    logging.info("Все фоновые задачи завершены")
    # Устанавливаем флаг завершения, если он еще не установлен
    shutdown_event.set()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Принудительное завершение работы")
        try:
            # Запускаем корректное завершение работы
            asyncio.run(shutdown())
        except Exception as e:
            logging.error(f"Ошибка при завершении работы: {e}")
    except Exception as e:
        logging.error(f"Необработанное исключение: {e}")
        sys.exit(1)
