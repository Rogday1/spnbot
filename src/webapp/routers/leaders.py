from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from src.database.db import get_session
from src.database.repositories import UserRepository
from src.utils.cache import cache

class LeaderData(BaseModel):
    rank: int
    id: int
    name: str
    score: int
    
class LeadersList(BaseModel):
    leaders: List[LeaderData]

# Создаем роутер
router = APIRouter(prefix="/api", tags=["leaders"])

# API для получения списка лидеров
@router.get("/leaders", response_model=LeadersList)
async def get_leaders(
    limit: int = Query(10, description="Количество лидеров", ge=1, le=100),
    reset_cache: bool = Query(False, description="Сбросить кэш лидеров"),
    user_id: Optional[int] = Query(None, description="ID текущего пользователя"),
    session: AsyncSession = Depends(get_session)
):
    """Получает список лидеров по очкам"""
    user_repo = UserRepository(session)
    
    # Если запрошен сброс кэша, удаляем ключи для всех связанных с лидерами кэшей
    if reset_cache:
        # Удаляем общий ключ кэша лидеров
        await cache.delete("get_leaders")
        
        # Удаляем кэш базового списка лидеров для всех лимитов от 1 до 100
        # (здесь мы удаляем все возможные кэши, которые могли быть созданы)
        for i in range(1, 101):
            await cache.delete(f"leaders_base:{i}")
    
    # Получаем список лидеров
    leaders = await user_repo.get_leaders(limit=limit, current_user_id=user_id)
    
    return LeadersList(leaders=leaders) 