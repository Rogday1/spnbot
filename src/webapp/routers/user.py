from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone
import logging

from src.database.db import get_session
from src.database.repositories import UserRepository
from src.bot.utils.subscription import check_all_subscriptions
from src.config import settings

# Модели Pydantic для API
class UserData(BaseModel):
    user_id: int
    tickets: int
    spins_count: int
    time_until_free_spin: str
    nickname: Optional[str] = None
    nickname_webapp: Optional[str] = None
    referral_count: int = 0  # Число приглашенных друзей
    
class ReferralData(BaseModel):
    id: int
    name: str
    balance: int
    
class ReferralsList(BaseModel):
    referrals: List[ReferralData]
    total_count: int

class NicknameRequest(BaseModel):
    nickname: str
    
class NicknameResponse(BaseModel):
    success: bool
    message: Optional[str] = None

class ReferralStats(BaseModel):
    total_referrals: int
    top_referrals: List[ReferralData]

class UpdateNicknameRequest(BaseModel):
    nickname: str

# Создаем роутер
router = APIRouter(prefix="/api/user", tags=["user"])

# API для получения данных пользователя
@router.get("/{user_id}", response_model=UserData)
async def get_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """Получает данные пользователя"""
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    
    # Если никнейм не установлен, автоматически используем имя из Telegram
    if not user.nickname and user.first_name:
        user.nickname = user.first_name
        await user_repo.update_user(user)
    
    # Проверяем, можно ли получить бесплатный прокрут
    # И даем его только если у пользователя 0 билетов
    if user.can_get_free_spin() and user.tickets == 0:
        await user_repo.add_free_spin(user_id)
        # Получаем обновленные данные пользователя
        user = await user_repo.get_user_by_id(user_id)
    
    return UserData(
        user_id=user.id,
        tickets=user.tickets,
        spins_count=user.spins_count,
        time_until_free_spin=user.get_time_until_free_spin(),
        nickname=user.nickname,
        nickname_webapp=user.nickname_webapp,
        referral_count=getattr(user, 'referral_count', 0)  # Используем getattr для безопасного получения
    )

# Добавить эндпоинт для проверки подписки на каналы
@router.post("/check_subscription", response_model=Dict[str, Any])
async def check_subscription(request: Dict[str, Any], request_obj: Request):
    """
    Проверяет подписку пользователя на обязательные каналы.
    
    Args:
        request: Данные запроса с user_id и initData
        request_obj: Объект запроса FastAPI
    
    Returns:
        Dict[str, Any]: Результат проверки с флагом подписки и списком каналов
    """
    try:
        # Получаем ID пользователя из запроса
        user_id = request.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="Не указан ID пользователя")
        
        # Получаем экземпляр бота из состояния приложения
        bot = request_obj.app.state.bot
        
        if not bot:
            raise HTTPException(status_code=500, detail="Бот не инициализирован")
        
        # Если список обязательных каналов пуст, считаем что пользователь подписан
        if not settings.REQUIRED_CHANNELS:
            return {"subscribed": True, "channels": []}
        
        # Проверяем подписку на все обязательные каналы
        all_subscribed, channels_info = await check_all_subscriptions(bot, user_id)
        
        # Преобразуем channels_info для отправки в ответе
        channels_for_response = []
        for channel in channels_info:
            # Формируем URL для подписки
            url = channel.get('invite_link')
            if not url and channel.get('username'):
                url = f"https://t.me/{channel['username']}"
            elif not url:
                continue
                
            channels_for_response.append({
                "title": channel.get('title', 'Канал'),
                "url": url,
                "is_subscribed": channel.get('is_subscribed', False)
            })
        
        return {
            "subscribed": all_subscribed,
            "channels": channels_for_response
        }
        
    except Exception as e:
        logging.error(f"Ошибка при проверке подписки: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

# API для обновления никнейма пользователя (старый эндпоинт - для обратной совместимости)
@router.post("/{user_id}/nickname", response_model=Dict[str, Any])
async def update_nickname_old(
    user_id: int, 
    data: NicknameRequest, 
    session: AsyncSession = Depends(get_session)
):
    """Устаревший эндпоинт обновления никнейма (для обратной совместимости)"""
    try:
        # Проверяем никнейм на корректность
        if len(data.nickname) < 2:
            return {"success": False, "message": "Никнейм слишком короткий (минимум 2 символа)"}
            
        if len(data.nickname) > 20:
            return {"success": False, "message": "Никнейм слишком длинный (максимум 20 символов)"}
        
        # Проверяем, что никнейм содержит только допустимые символы
        import re
        if not re.match(r'^[a-zA-Zа-яА-Я0-9_\s]+$', data.nickname):
            return {"success": False, "message": "Никнейм может содержать только буквы, цифры, пробелы и символ подчеркивания"}
        
        # Обновляем никнейм в базе данных
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        # Устанавливаем никнейм из веб-приложения
        user.nickname_webapp = data.nickname
        await user_repo.update_user(user)
        
        # Логируем успешное обновление
        logging.info(f"Никнейм пользователя {user_id} обновлен на '{data.nickname}' через устаревший эндпоинт")
        
        return {"success": True, "message": "Никнейм успешно обновлен"}
        
    except Exception as e:
        logging.error(f"Ошибка при обновлении никнейма: {e}")
        return {"success": False, "message": "Произошла ошибка при обновлении никнейма"}

# API для обновления никнейма пользователя (новый эндпоинт)
@router.post("/{user_id}/update-nickname", response_model=UserData)
async def update_nickname(
    user_id: int, 
    data: UpdateNicknameRequest, 
    session: AsyncSession = Depends(get_session)
):
    """Обновляет никнейм пользователя"""
    # Проверяем никнейм на корректность
    if len(data.nickname) < 2:
        raise HTTPException(status_code=400, detail="Никнейм слишком короткий (минимум 2 символа)")
    if len(data.nickname) > 20:
        raise HTTPException(status_code=400, detail="Никнейм слишком длинный (максимум 20 символов)")
    
    # Проверяем, что никнейм содержит только допустимые символы
    import re
    if not re.match(r'^[a-zA-Zа-яА-Я0-9_\s]+$', data.nickname):
        raise HTTPException(
            status_code=400, 
            detail="Никнейм может содержать только буквы, цифры, пробелы и символ подчеркивания"
        )
    
    # Обновляем никнейм в базе данных
    user_repo = UserRepository(session)
    user = await user_repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Устанавливаем никнейм из веб-приложения
    user.nickname_webapp = data.nickname
    await user_repo.update_user(user)
    
    # Получаем обновленные данные
    updated_user = await user_repo.get_user_by_id(user_id)
    
    return UserData(
        user_id=updated_user.id,
        tickets=updated_user.tickets,
        spins_count=updated_user.spins_count,
        time_until_free_spin=updated_user.get_time_until_free_spin(),
        nickname=updated_user.nickname,
        nickname_webapp=updated_user.nickname_webapp,
        referral_count=getattr(updated_user, 'referral_count', 0)
    )

# API для получения рефералов пользователя
@router.get("/{user_id}/referrals", response_model=ReferralsList)
async def get_user_referrals(
    user_id: int, 
    limit: int = Query(10, ge=1, le=100), 
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session)
):
    """Получает список рефералов пользователя"""
    user_repo = UserRepository(session)
    
    # Получаем список рефералов
    referrals = await user_repo.get_referrals(user_id, limit, offset)
    
    # Получаем общее количество рефералов
    total_count = await user_repo.count_referrals(user_id)
    
    return ReferralsList(
        referrals=referrals,
        total_count=total_count
    )

# API для получения статистики по рефералам
@router.get("/{user_id}/referral-stats", response_model=ReferralStats)
async def get_user_referral_stats(
    user_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Получает статистику по рефералам пользователя"""
    user_repo = UserRepository(session)
    
    # Получаем статистику
    stats = await user_repo.get_referral_stats(user_id)
    
    return ReferralStats(
        total_referrals=stats["total_referrals"],
        top_referrals=stats["top_referrals"]
    ) 