from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime

from src.database.db import Base


class Giveaway(Base):
    __tablename__ = "giveaways"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    prize = Column(String, nullable=True)
    status = Column(String, nullable=False, default="draft")  # draft | active | finished
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(BigInteger, nullable=True)  # admin user id
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def is_active(self) -> bool:
        now = datetime.utcnow()
        if self.status != "active":
            return False
        if self.starts_at and now < self.starts_at.replace(tzinfo=None):
            return False
        if self.ends_at and now > self.ends_at.replace(tzinfo=None):
            return False
        return True


