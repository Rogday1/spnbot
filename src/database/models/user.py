from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta

from src.database.db import Base
from src.config import settings


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    nickname = Column(String, nullable=True)  # Никнейм из Telegram
    nickname_webapp = Column(String, nullable=True)  # Никнейм, введенный в веб-приложении
    is_admin = Column(Boolean, default=False)
    spins_count = Column(Integer, default=0)
    tickets = Column(Integer, default=0)  # Количество билетов (прокрутов), начальное значение 0
    last_free_spin = Column(DateTime, default=datetime.now() - timedelta(days=1))  # Время последнего бесплатного прокрута
    referral_count = Column(Integer, default=0)  # Количество приглашенных пользователей
    referred_by = Column(BigInteger, nullable=True)  # ID пользователя, который пригласил текущего
    referral_earnings = Column(Integer, default=0)  # Заработок от рефералов
    referral_bonus_tickets = Column(Integer, default=0)  # Бонусные билеты от рефералов
    total_referral_earnings = Column(Integer, default=0)  # Общий заработок от рефералов за всё время
    
    def can_spin(self):
        """Проверяет, может ли пользователь сделать прокрут"""
        return self.tickets > 0
    
    def can_get_free_spin(self):
        """Проверяет, может ли пользователь получить бесплатный прокрут"""
        now = datetime.now()
        time_passed = now - self.last_free_spin
        return time_passed.total_seconds() >= settings.FREE_SPIN_INTERVAL
    
    def get_time_until_free_spin(self):
        """Возвращает оставшееся время до следующего бесплатного прокрута в формате ЧЧ:ММ"""
        now = datetime.now()
        next_free_spin = self.last_free_spin + timedelta(seconds=settings.FREE_SPIN_INTERVAL)
        
        if now >= next_free_spin:
            return "00:00"
        
        remaining = next_free_spin - now
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        return f"{hours:02d}:{minutes:02d}"
    
    def add_ticket(self):
        """Добавляет билет пользователю"""
        self.tickets += 1
    
    def use_ticket(self, win_value: int = 0):
        """
        Использует билет для прокрута
        
        Args:
            win_value (int): Выигранное значение, которое будет добавлено к балансу
        
        Returns:
            bool: True, если билет был успешно использован, иначе False
        """
        if self.tickets > 0:
            self.tickets -= 1
            self.spins_count += win_value  # Добавляем выигранное значение к балансу
            # Обновляем время последнего бесплатного прокрута только если использовали последний билет
            if self.tickets == 0:
                self.reset_free_spin_timer()
            return True
        return False
    
    def reset_free_spin_timer(self):
        """Сбрасывает таймер бесплатного прокрута"""
        self.last_free_spin = datetime.now()
    
    def add_referral(self):
        """Добавляет реферала"""
        self.referral_count += 1
        # Даём бонус за каждого реферала
        self.referral_bonus_tickets += 1
        self.tickets += 1
    
    def add_referral_earnings(self, amount: int):
        """Добавляет заработок от реферала"""
        self.referral_earnings += amount
        self.total_referral_earnings += amount
        self.spins_count += amount
    
    def get_referral_stats(self):
        """Возвращает статистику по рефералам"""
        return {
            'referral_count': self.referral_count,
            'referral_earnings': self.referral_earnings,
            'referral_bonus_tickets': self.referral_bonus_tickets,
            'total_referral_earnings': self.total_referral_earnings
        }
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, tickets={self.tickets}, spins_count={self.spins_count})>" 