from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import logging

from src.database.db import get_session
from src.database.repositories.giveaway_repository import GiveawayRepository, GiveawayEntryRepository


class GiveawayOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    prize: Optional[str] = None
    status: str
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None


class CreateGiveawayIn(BaseModel):
    title: str
    description: Optional[str] = None
    prize: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None


router = APIRouter(prefix="/api/giveaways", tags=["giveaways"])


@router.get("/active", response_model=List[GiveawayOut])
async def list_active(session: AsyncSession = Depends(get_session)):
    repo = GiveawayRepository(session)
    items = await repo.list_active()
    return [
        GiveawayOut(
            id=i.id, title=i.title, description=i.description, prize=i.prize,
            status=i.status, starts_at=i.starts_at.isoformat() if i.starts_at else None,
            ends_at=i.ends_at.isoformat() if i.ends_at else None
        ) for i in items
    ]


@router.post("/{giveaway_id}/join", response_model=Dict[str, Any])
async def join_giveaway(giveaway_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    # user_id берем из middleware TelegramAuthMiddleware -> request.state.user_id
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Нет авторизации Telegram")

    g_repo = GiveawayRepository(session)
    e_repo = GiveawayEntryRepository(session)

    giveaway = await g_repo.get_by_id(giveaway_id)
    if not giveaway or giveaway.status != 'active':
        raise HTTPException(status_code=404, detail="Розыгрыш не найден или не активен")

    await e_repo.join(giveaway_id, user_id)
    total = await e_repo.count_entries(giveaway_id)
    return {"success": True, "joined": True, "total": total}


# Примитивные админ-операции (под защитой общих middleware/фильтров IP/токена, если добавим)
@router.post("/admin/create", response_model=GiveawayOut)
async def admin_create(data: CreateGiveawayIn, request: Request, session: AsyncSession = Depends(get_session)):
    created_by = getattr(request.state, 'user_id', None)
    repo = GiveawayRepository(session)
    item = await repo.create(data.title, data.description, data.prize, created_by, None, None)
    return GiveawayOut(
        id=item.id, title=item.title, description=item.description, prize=item.prize,
        status=item.status, starts_at=None, ends_at=None
    )

@router.post("/admin/publish/{giveaway_id}")
async def admin_publish(giveaway_id: int, session: AsyncSession = Depends(get_session)):
    repo = GiveawayRepository(session)
    ok = await repo.set_status(giveaway_id, 'active')
    return {"success": ok}

@router.post("/admin/finish/{giveaway_id}")
async def admin_finish(giveaway_id: int, session: AsyncSession = Depends(get_session)):
    repo = GiveawayRepository(session)
    result = await repo.finish_and_draw(giveaway_id, winners_count=1)
    return {"success": True, **result}


