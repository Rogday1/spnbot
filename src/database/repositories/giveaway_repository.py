from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import random
import logging

from src.database.models import Giveaway, GiveawayEntry


class GiveawayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, title: str, description: str | None, prize: str | None, created_by: int | None,
                     starts_at=None, ends_at=None) -> Giveaway:
        giveaway = Giveaway(
            title=title,
            description=description,
            prize=prize,
            status="draft",
            starts_at=starts_at,
            ends_at=ends_at,
            created_by=created_by,
        )
        self.session.add(giveaway)
        await self.session.commit()
        await self.session.refresh(giveaway)
        return giveaway

    async def set_status(self, giveaway_id: int, status: str) -> bool:
        stmt = update(Giveaway).where(Giveaway.id == giveaway_id).values(status=status)
        await self.session.execute(stmt)
        await self.session.commit()
        return True

    async def get_by_id(self, giveaway_id: int) -> Optional[Giveaway]:
        result = await self.session.execute(select(Giveaway).where(Giveaway.id == giveaway_id))
        return result.scalar_one_or_none()

    async def list_active(self) -> List[Giveaway]:
        # status=active и дата в окне
        result = await self.session.execute(
            select(Giveaway).where(Giveaway.status == "active").order_by(Giveaway.ends_at.is_(True))
        )
        return result.scalars().all()

    async def list_all(self, limit: int = 50) -> List[Giveaway]:
        result = await self.session.execute(select(Giveaway).order_by(Giveaway.id.desc()).limit(limit))
        return result.scalars().all()

    async def finish_and_draw(self, giveaway_id: int, winners_count: int = 1) -> dict:
        # Получаем список участников
        result = await self.session.execute(
            select(GiveawayEntry.user_id).where(GiveawayEntry.giveaway_id == giveaway_id)
        )
        users = [row[0] for row in result.fetchall()]

        # Выбираем победителей
        winners = []
        if users:
            winners_count = max(1, min(winners_count, len(users)))
            winners = random.sample(users, winners_count)

        await self.set_status(giveaway_id, "finished")
        logging.info(f"Giveaway {giveaway_id} finished. Winners: {winners}")
        return {"winners": winners, "total": len(users)}


class GiveawayEntryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def has_joined(self, giveaway_id: int, user_id: int) -> bool:
        result = await self.session.execute(
            select(func.count()).select_from(GiveawayEntry).where(
                GiveawayEntry.giveaway_id == giveaway_id,
                GiveawayEntry.user_id == user_id
            )
        )
        return (result.scalar() or 0) > 0

    async def join(self, giveaway_id: int, user_id: int) -> bool:
        if await self.has_joined(giveaway_id, user_id):
            return True
        entry = GiveawayEntry(giveaway_id=giveaway_id, user_id=user_id)
        self.session.add(entry)
        await self.session.commit()
        return True

    async def count_entries(self, giveaway_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(GiveawayEntry).where(GiveawayEntry.giveaway_id == giveaway_id)
        )
        return result.scalar() or 0


