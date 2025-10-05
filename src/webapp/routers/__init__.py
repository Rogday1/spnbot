"""
Пакет routers содержит модули маршрутизации для API FastAPI.
"""

from .user import router as user_router
from .game import router as game_router
from .leaders import router as leaders_router
from .giveaways import router as giveaways_router
from .subscription import router as subscription_router

__all__ = ['user_router', 'game_router', 'leaders_router', 'giveaways_router', 'subscription_router']
