from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Game


class GameRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_game(self, user_id: int, result: str) -> Game:
        """Создает запись об игре"""
        game = Game(user_id=user_id, result=result)
        self.session.add(game)
        await self.session.commit()
        await self.session.refresh(game)
        return game
    
    async def get_games_by_user(self, user_id: int, limit: int = 10) -> list[Game]:
        """Получает последние игры пользователя"""
        query = select(Game).where(Game.user_id == user_id).order_by(Game.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all() 