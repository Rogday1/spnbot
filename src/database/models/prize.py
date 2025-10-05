from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Boolean, Float, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from src.database.db import Base

class Prize(Base):
    __tablename__ = "prizes"

    id = Column(BigInteger, primary_key=True)
    name = Column(String, nullable=False)  # Название приза
    description = Column(Text, nullable=True)  # Описание приза
    value = Column(Integer, nullable=False)  # Стоимость приза в рублях
    probability = Column(Float, nullable=False, default=0.1)  # Вероятность выпадения (0.0 - 1.0)
    is_active = Column(Boolean, default=True)  # Активен ли приз
    image_url = Column(String, nullable=True)  # URL изображения приза
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связь с играми (статистика)
    games = relationship("Game", back_populates="prize")

    def __repr__(self):
        return f"<Prize(id={self.id}, name='{self.name}', value={self.value}, probability={self.probability})>"
