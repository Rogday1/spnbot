"""
Пакет routers содержит модули маршрутизации для API FastAPI.
"""

from .user import router as user_router
from .game import router as game_router
from .leaders import router as leaders_router

__all__ = ['user_router', 'game_router', 'leaders_router']
