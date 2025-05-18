import asyncio
import logging
import sys
import argparse
import os
from alembic.config import Config
from alembic import command

from src.database.db import init_db
from run_migrations import run_migrations


async def setup_database(recreate_daily_stats=False):
    """
    Настраивает базу данных с использованием Alembic миграций.
    
    Args:
        recreate_daily_stats (bool): Пересоздать таблицу daily_stats
    """
    try:
        logging.info("Настройка базы данных PostgreSQL...")
        
        # Применяем миграции с помощью Alembic
        success = run_migrations(upgrade=True)
        
        if not success:
            logging.error("Ошибка при применении миграций")
            return False
        
        # Если нужно пересоздать таблицу daily_stats
        if recreate_daily_stats:
            logging.info("Удаление таблицы daily_stats...")
            db_session = await init_db()
            async with db_session() as session:
                await session.execute("DROP TABLE IF EXISTS daily_stats CASCADE")
                await session.commit()
                logging.info("Таблица daily_stats удалена")
            
            # Применяем миграции снова для создания таблицы daily_stats
            success = run_migrations(upgrade=True)
            if not success:
                logging.error("Ошибка при повторном применении миграций")
                return False
        
        # Инициализируем соединение с базой данных
        await init_db()
        logging.info("База данных успешно настроена")
        return True
    
    except Exception as e:
        logging.error(f"Ошибка при настройке базы данных: {e}")
        return False


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description="Миграция базы данных PostgreSQL")
    parser.add_argument("--recreate-daily-stats", action="store_true", help="Пересоздать таблицу daily_stats")
    parser.add_argument("--debug", action="store_true", help="Включить режим отладки")
    args = parser.parse_args()
    
    # Устанавливаем уровень логирования
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Включен режим отладки")
    
    # Запуск настройки базы данных
    success = asyncio.run(setup_database(recreate_daily_stats=args.recreate_daily_stats))
    
    # Выход с соответствующим кодом
    sys.exit(0 if success else 1) 