from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
import logging

from src.database.models import DailyStats
from src.config import settings
from src.utils.cache import cached, cache


class DailyStatsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_today_stats(self) -> DailyStats:
        """
        Получает или создает запись статистики за текущий день
        
        Returns:
            DailyStats: Статистика за текущий день
        """
        try:
            today = date.today()
            
            # Пробуем получить из кэша
            cache_key = f"daily_stats:{today}"
            cached_stats = await cache.get(cache_key)
            if cached_stats:
                return cached_stats
            
            # Ищем запись за сегодня
            query = select(DailyStats).where(DailyStats.date == today)
            result = await self.session.execute(query)
            stats = result.scalars().first()
            
            # Если записи нет, создаем новую
            if not stats:
                stats = DailyStats(date=today)
                self.session.add(stats)
                await self.session.commit()
                await self.session.refresh(stats)
                logging.info(f"Создана новая запись статистики на {today}")
            
            # Кэшируем результат на короткое время
            await cache.set(cache_key, stats, ttl=60)  # Кэшируем на 1 минуту
            
            return stats
        except Exception as e:
            logging.error(f"Ошибка при получении статистики за сегодня: {e}")
            # Создаем временный объект, чтобы не нарушать работу приложения
            return DailyStats(date=date.today(), total_wins=0, spins_count=0)
    
    async def update_daily_stats(self, win_amount: int) -> bool:
        """
        Обновляет статистику за день после выигрыша
        
        Args:
            win_amount (int): Сумма выигрыша
            
        Returns:
            bool: True если обновление прошло успешно, иначе False
        """
        try:
            today = date.today()
            
            # Оптимизированный запрос на обновление без предварительной загрузки
            stmt = (
                update(DailyStats)
                .where(DailyStats.date == today)
                .values(
                    total_wins=DailyStats.total_wins + win_amount,
                    spins_count=DailyStats.spins_count + 1
                )
            )
            
            result = await self.session.execute(stmt)
            
            # Если запись не найдена, создаем новую
            if result.rowcount == 0:
                stats = DailyStats(
                    date=today,
                    total_wins=win_amount,
                    spins_count=1
                )
                self.session.add(stats)
            
            await self.session.commit()
            
            # Инвалидируем кэш
            await cache.delete(f"daily_stats:{today}")
            
            return True
        except Exception as e:
            logging.error(f"Ошибка при обновлении статистики за день: {e}")
            return False
    
    @cached(ttl=60)  # Кэшируем на 1 минуту
    async def get_win_percentage(self) -> float:
        """
        Рассчитывает процент использованного дневного лимита выигрышей
        
        Returns:
            float: Процент от 0.0 до 1.0
        """
        try:
            stats = await self.get_today_stats()
            max_win = settings.MAX_WIN_PER_DAY if hasattr(settings, 'MAX_WIN_PER_DAY') else 5000
            
            # Рассчитываем процент
            percentage = stats.total_wins / max_win
            
            # Ограничиваем значение от 0.0 до 1.0
            return min(max(percentage, 0.0), 1.0)
        except Exception as e:
            logging.error(f"Ошибка при расчете процента использованного лимита: {e}")
            return 0.0 