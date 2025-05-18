from sqlalchemy import Column, String, Integer, BigInteger, DateTime, ForeignKey
from datetime import datetime

from src.database.db import Base


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    result = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<Game(id={self.id}, user_id={self.user_id}, result={self.result})>" 