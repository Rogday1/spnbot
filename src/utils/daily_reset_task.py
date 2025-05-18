import asyncio
import logging
from datetime import datetime, date, time, timedelta
from sqlalchemy import delete

from src.database.db import async_session
from src.database.models import DailyStats
from src.utils.cache import cache


async def reset_daily_stats():
    """
    Сбрасывает ежедневную статистику в начале нового дня.
    Создает новую запись для текущего дня.
    """
    try:
        logging.info("Запуск задачи сброса ежедневной статистики")
        
        # Получаем текущую дату
        today = date.today()
        
        async with async_session() as session:
            # Проверяем, есть ли запись за сегодня
            from sqlalchemy import select
            query = select(DailyStats).where(DailyStats.date == today)
            result = await session.execute(query)
            stats = result.scalars().first()
            
            # Если записи за сегодня нет, создаем новую
            if not stats:
                new_stats = DailyStats(date=today)
                session.add(new_stats)
                await session.commit()
                logging.info(f"Создана новая запись статистики на {today}")
            
            # Очищаем кэш
            await cache.delete(f"daily_stats:{today}")
            await cache.delete("get_win_percentage")
            
            logging.info("Задача сброса ежедневной статистики завершена")
    except Exception as e:
        logging.error(f"Ошибка при сбросе ежедневной статистики: {e}")


async def schedule_daily_reset():
    """
    Планирует ежедневный сброс статистики в полночь.
    """
    try:
        while True:
            # Получаем текущее время
            now = datetime.now()
            
            # Вычисляем время до следующей полуночи
            tomorrow = datetime.combine(now.date() + timedelta(days=1), time.min)
            seconds_until_midnight = (tomorrow - now).total_seconds()
            
            # Логируем время до следующего сброса
            hours, remainder = divmod(seconds_until_midnight, 3600)
            minutes, seconds = divmod(remainder, 60)
            logging.info(f"Следующий сброс статистики через {int(hours)}:{int(minutes):02d}:{int(seconds):02d}")
            
            # Ждем до полуночи
            await asyncio.sleep(seconds_until_midnight)
            
            # Выполняем сброс статистики
            await reset_daily_stats()
            
            # Ждем небольшое время, чтобы не запустить задачу дважды
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        logging.info("Задача планирования сброса статистики отменена")
    except Exception as e:
        logging.error(f"Ошибка в задаче планирования сброса статистики: {e}")
        # Перезапускаем задачу через 5 минут в случае ошибки
        await asyncio.sleep(300)
        asyncio.create_task(schedule_daily_reset()) 