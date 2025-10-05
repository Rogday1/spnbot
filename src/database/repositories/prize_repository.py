from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging
from typing import List, Optional

from src.database.models import Prize, Game
from src.utils.cache import cache, cached

class PrizeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_prize(self, name: str, description: str, value: int, probability: float, image_url: str = None) -> Prize:
        """
        Создает новый приз
        
        Args:
            name: Название приза
            description: Описание приза
            value: Стоимость приза в рублях
            probability: Вероятность выпадения (0.0 - 1.0)
            image_url: URL изображения приза
            
        Returns:
            Prize: Созданный приз
        """
        try:
            prize = Prize(
                name=name,
                description=description,
                value=value,
                probability=probability,
                image_url=image_url
            )
            self.session.add(prize)
            await self.session.commit()
            await self.session.refresh(prize)
            
            # Очищаем кэш
            await cache.delete("prizes:all")
            await cache.delete("prizes:active")
            
            logging.info(f"Создан приз: {name} (ID: {prize.id})")
            return prize
        except Exception as e:
            await self.session.rollback()
            logging.error(f"Ошибка при создании приза: {e}")
            raise

    async def get_prize(self, prize_id: int) -> Optional[Prize]:
        """
        Получает приз по ID
        
        Args:
            prize_id: ID приза
            
        Returns:
            Prize или None
        """
        try:
            result = await self.session.execute(
                select(Prize).where(Prize.id == prize_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logging.error(f"Ошибка при получении приза {prize_id}: {e}")
            return None

    @cached(ttl=300)  # Кэшируем на 5 минут
    async def get_all_prizes(self) -> List[Prize]:
        """
        Получает все призы
        
        Returns:
            List[Prize]: Список всех призов
        """
        try:
            result = await self.session.execute(
                select(Prize).order_by(Prize.created_at.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logging.error(f"Ошибка при получении всех призов: {e}")
            return []

    @cached(ttl=300)  # Кэшируем на 5 минут
    async def get_active_prizes(self) -> List[Prize]:
        """
        Получает только активные призы
        
        Returns:
            List[Prize]: Список активных призов
        """
        try:
            result = await self.session.execute(
                select(Prize).where(Prize.is_active == True).order_by(Prize.value.asc())
            )
            return result.scalars().all()
        except Exception as e:
            logging.error(f"Ошибка при получении активных призов: {e}")
            return []

    async def update_prize(self, prize_id: int, **kwargs) -> bool:
        """
        Обновляет приз
        
        Args:
            prize_id: ID приза
            **kwargs: Поля для обновления
            
        Returns:
            bool: True если успешно
        """
        try:
            # Добавляем updated_at
            kwargs['updated_at'] = datetime.now()
            
            await self.session.execute(
                update(Prize)
                .where(Prize.id == prize_id)
                .values(**kwargs)
            )
            await self.session.commit()
            
            # Очищаем кэш
            await cache.delete("prizes:all")
            await cache.delete("prizes:active")
            await cache.delete(f"prize:{prize_id}")
            
            logging.info(f"Обновлен приз {prize_id}")
            return True
        except Exception as e:
            await self.session.rollback()
            logging.error(f"Ошибка при обновлении приза {prize_id}: {e}")
            return False

    async def delete_prize(self, prize_id: int) -> bool:
        """
        Удаляет приз (мягкое удаление - деактивирует)
        
        Args:
            prize_id: ID приза
            
        Returns:
            bool: True если успешно
        """
        try:
            await self.session.execute(
                update(Prize)
                .where(Prize.id == prize_id)
                .values(is_active=False, updated_at=datetime.now())
            )
            await self.session.commit()
            
            # Очищаем кэш
            await cache.delete("prizes:all")
            await cache.delete("prizes:active")
            await cache.delete(f"prize:{prize_id}")
            
            logging.info(f"Деактивирован приз {prize_id}")
            return True
        except Exception as e:
            await self.session.rollback()
            logging.error(f"Ошибка при удалении приза {prize_id}: {e}")
            return False

    async def get_prize_statistics(self, prize_id: int) -> dict:
        """
        Получает статистику по призу
        
        Args:
            prize_id: ID приза
            
        Returns:
            dict: Статистика приза
        """
        try:
            # Количество выигрышей этого приза
            wins_count = await self.session.execute(
                select(func.count(Game.id))
                .where(Game.prize_id == prize_id)
                .where(Game.is_win == True)
            )
            wins = wins_count.scalar() or 0
            
            # Общая стоимость выигрышей
            total_value = await self.session.execute(
                select(func.sum(Game.win_amount))
                .where(Game.prize_id == prize_id)
                .where(Game.is_win == True)
            )
            total_value = total_value.scalar() or 0
            
            return {
                "wins_count": wins,
                "total_value": total_value,
                "average_value": total_value / wins if wins > 0 else 0
            }
        except Exception as e:
            logging.error(f"Ошибка при получении статистики приза {prize_id}: {e}")
            return {"wins_count": 0, "total_value": 0, "average_value": 0}

    async def get_prizes_for_spin(self) -> List[Prize]:
        """
        Получает призы для рулетки (только активные, отсортированные по вероятности)
        
        Returns:
            List[Prize]: Список призов для рулетки
        """
        try:
            result = await self.session.execute(
                select(Prize)
                .where(Prize.is_active == True)
                .order_by(Prize.probability.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logging.error(f"Ошибка при получении призов для рулетки: {e}")
            return []
