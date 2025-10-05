from sqlalchemy import Column, String, Integer, BigInteger, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from src.database.db import Base


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    result = Column(String, nullable=False)
    prize_id = Column(BigInteger, ForeignKey("prizes.id"), nullable=True)  # Связь с призом
    is_win = Column(Boolean, default=False)  # Выигрыш или нет
    win_amount = Column(Integer, default=0)  # Сумма выигрыша
    created_at = Column(DateTime, default=datetime.now)
    
    # Связь с призом
    prize = relationship("Prize", back_populates="games")
    
    def __repr__(self):
        return f"<Game(id={self.id}, user_id={self.user_id}, result={self.result}, is_win={self.is_win})>" 