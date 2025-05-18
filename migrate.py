import asyncio
import logging
import sys
import argparse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.database.db import init_db, Base, engine
from src.database.models import User, Game, DailyStats


async def create_tables(recreate_daily_stats=False):
    """
    Создает все таблицы в базе данных.
    
    Args:
        recreate_daily_stats (bool): Пересоздать таблицу daily_stats
    """
    try:
        logging.info("Создание таблиц в базе данных...")
        
        # Если нужно пересоздать таблицу daily_stats
        if recreate_daily_stats:
            logging.info("Удаление таблицы daily_stats...")
            async with engine.begin() as conn:
                await conn.execute(text("DROP TABLE IF EXISTS daily_stats"))
                logging.info("Таблица daily_stats удалена")
        
        async with engine.begin() as conn:
            # Создаем таблицы
            await conn.run_sync(Base.metadata.create_all)
        
        logging.info("Таблицы успешно созданы")
        
        # Проверяем, что таблицы действительно созданы
        db_session = await init_db()
        
        try:
            # Проверяем наличие таблиц
            async with db_session() as session:
                session: AsyncSession
                # Здесь можно выполнить проверочные запросы к базе данных
                pass
                
            logging.info("Подключение к базе данных успешно проверено")
        except Exception as e:
            logging.error(f"Ошибка при проверке подключения к базе данных: {e}")
    
    except Exception as e:
        logging.error(f"Ошибка при создании таблиц: {e}")
        raise


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description="Миграция базы данных")
    parser.add_argument("--recreate-daily-stats", action="store_true", help="Пересоздать таблицу daily_stats")
    args = parser.parse_args()
    
    # Запуск миграции
    asyncio.run(create_tables(recreate_daily_stats=args.recreate_daily_stats)) 