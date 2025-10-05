from sqlalchemy import Column, Integer, Date, BigInteger, Text
from datetime import date
import json
import os

from src.database.db import Base

# Определяем тип БД
is_sqlite = os.getenv('DATABASE_URL', '').startswith('sqlite')

# Импортируем JSONB только для PostgreSQL
if not is_sqlite:
    from sqlalchemy.dialects.postgresql import JSONB


class DailyStats(Base):
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, default=date.today, index=True, unique=True)
    total_wins = Column(BigInteger, default=0)  # Общая сумма выигрышей за день
    spins_count = Column(Integer, default=0)    # Количество прокрутов за день
    
    # Используем Text для SQLite, JSONB для PostgreSQL
    sector_stats = Column(Text, nullable=True) if is_sqlite else Column(JSONB, nullable=True)
    
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