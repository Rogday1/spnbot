from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
import logging

from src.database.db import get_session
from src.database.repositories.sponsor_channel_repository import SponsorChannelRepository


class SubscriptionCheckResponse(BaseModel):
    is_subscribed: bool
    required_channels: List[Dict[str, Any]]
    missing_channels: List[Dict[str, Any]]


router = APIRouter(prefix="/api/subscription", tags=["subscription"])


@router.get("/check", response_model=SubscriptionCheckResponse)
async def check_subscription(request: Request, session: AsyncSession = Depends(get_session)):
    """Проверяет подписку пользователя на обязательные каналы"""
    # user_id берем из middleware TelegramAuthMiddleware -> request.state.user_id
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Нет авторизации Telegram")
    
    try:
        channel_repo = SponsorChannelRepository(session)
        required_channels = await channel_repo.get_required_channels()
        
        if not required_channels:
            return SubscriptionCheckResponse(
                is_subscribed=True,
                required_channels=[],
                missing_channels=[]
            )
        
        # Здесь должна быть логика проверки подписки через Telegram Bot API
        # Пока что возвращаем заглушку
        missing_channels = []
        for channel in required_channels:
            missing_channels.append({
                "id": channel.channel_id,
                "title": channel.channel_title,
                "url": channel.channel_url
            })
        
        return SubscriptionCheckResponse(
            is_subscribed=len(missing_channels) == 0,
            required_channels=[{
                "id": ch.channel_id,
                "title": ch.channel_title,
                "url": ch.channel_url
            } for ch in required_channels],
            missing_channels=missing_channels
        )
        
    except Exception as e:
        logging.error(f"Ошибка при проверке подписки: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при проверке подписки")


@router.get("/channels", response_model=List[Dict[str, Any]])
async def get_required_channels(session: AsyncSession = Depends(get_session)):
    """Получает список обязательных каналов"""
    try:
        channel_repo = SponsorChannelRepository(session)
        channels = await channel_repo.get_required_channels()
        
        return [{
            "id": channel.channel_id,
            "title": channel.channel_title,
            "url": channel.channel_url,
            "required": channel.is_required
        } for channel in channels]
        
    except Exception as e:
        logging.error(f"Ошибка при получении каналов: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении каналов")
