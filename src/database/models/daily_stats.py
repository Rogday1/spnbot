from sqlalchemy import Column, Integer, Date, BigInteger, JSON, Text
from sqlalchemy.dialects.postgresql import JSONB
from datetime import date
import json

from src.database.db import Base, is_sqlite


class DailyStats(Base):
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, default=date.today, index=True, unique=True)
    total_wins = Column(BigInteger, default=0)  # Общая сумма выигрышей за день
    spins_count = Column(Integer, default=0)    # Количество прокрутов за день
    
    # Используем JSONB для PostgreSQL и TEXT для SQLite
    sector_stats = Column(JSONB if not is_sqlite else Text, nullable=True)
    
    def __repr__(self):
        return f"<DailyStats(date={self.date}, total_wins={self.total_wins}, spins_count={self.spins_count})>"
    
    # Методы для работы с JSON в SQLite
    def get_sector_stats(self):
        """Получает статистику по секторам с учетом типа БД"""
        if is_sqlite and self.sector_stats and isinstance(self.sector_stats, str):
            try:
                return json.loads(self.sector_stats)
            except json.JSONDecodeError:
                return {}
        return self.sector_stats or {}
    
    def set_sector_stats(self, stats_dict):
        """Устанавливает статистику по секторам с учетом типа БД"""
        if is_sqlite:
            self.sector_stats = json.dumps(stats_dict)
        else:
            self.sector_stats = stats_dict 