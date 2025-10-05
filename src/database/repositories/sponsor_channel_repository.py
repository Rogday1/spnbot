from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging

from src.database.models.sponsor_channel import SponsorChannel


class SponsorChannelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_channel(self, channel_id: str, channel_title: str, channel_url: str = None, 
                           is_required: bool = True, created_by: int = None) -> SponsorChannel:
        """Создает новый канал-спонсор"""
        channel = SponsorChannel(
            channel_id=channel_id,
            channel_title=channel_title,
            channel_url=channel_url,
            is_required=is_required,
            created_by=created_by
        )
        self.session.add(channel)
        await self.session.commit()
        await self.session.refresh(channel)
        return channel

    async def get_channel(self, channel_id: str) -> Optional[SponsorChannel]:
        """Получает канал по ID"""
        result = await self.session.execute(
            select(SponsorChannel).where(SponsorChannel.channel_id == channel_id)
        )
        return result.scalar_one_or_none()

    async def get_all_channels(self) -> List[SponsorChannel]:
        """Получает все каналы"""
        result = await self.session.execute(
            select(SponsorChannel).order_by(SponsorChannel.created_at.desc())
        )
        return result.scalars().all()

    async def get_required_channels(self) -> List[SponsorChannel]:
        """Получает только обязательные каналы"""
        result = await self.session.execute(
            select(SponsorChannel).where(
                SponsorChannel.is_active == True,
                SponsorChannel.is_required == True
            ).order_by(SponsorChannel.created_at.desc())
        )
        return result.scalars().all()

    async def update_channel(self, channel_id: str, **kwargs) -> bool:
        """Обновляет канал"""
        try:
            stmt = update(SponsorChannel).where(
                SponsorChannel.channel_id == channel_id
            ).values(**kwargs)
            await self.session.execute(stmt)
            await self.session.commit()
            return True
        except Exception as e:
            logging.error(f"Ошибка при обновлении канала {channel_id}: {e}")
            return False

    async def delete_channel(self, channel_id: str) -> bool:
        """Удаляет канал"""
        try:
            stmt = delete(SponsorChannel).where(SponsorChannel.channel_id == channel_id)
            await self.session.execute(stmt)
            await self.session.commit()
            return True
        except Exception as e:
            logging.error(f"Ошибка при удалении канала {channel_id}: {e}")
            return False

    async def toggle_channel_status(self, channel_id: str) -> bool:
        """Переключает статус канала (активен/неактивен)"""
        channel = await self.get_channel(channel_id)
        if not channel:
            return False
        
        return await self.update_channel(channel_id, is_active=not channel.is_active)

    async def toggle_required_status(self, channel_id: str) -> bool:
        """Переключает обязательность канала"""
        channel = await self.get_channel(channel_id)
        if not channel:
            return False
        
        return await self.update_channel(channel_id, is_required=not channel.is_required)
