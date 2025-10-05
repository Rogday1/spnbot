from sqlalchemy import Column, String, Integer, DateTime, Boolean, BigInteger
from datetime import datetime
from src.database.db import Base


class SponsorChannel(Base):
    __tablename__ = "sponsor_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(String, nullable=False, unique=True)  # ID канала (например, @channel_name)
    channel_title = Column(String, nullable=False)  # Название канала
    channel_url = Column(String, nullable=True)  # URL канала
    is_active = Column(Boolean, default=True)  # Активен ли канал
    is_required = Column(Boolean, default=True)  # Обязательна ли подписка
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(BigInteger, nullable=False)  # ID администратора, который добавил канал

    def __repr__(self):
        return f"<SponsorChannel(id={self.id}, channel_id='{self.channel_id}', title='{self.channel_title}', required={self.is_required})>"
