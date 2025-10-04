from sqlalchemy import Column, BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from src.database.db import Base


class GiveawayEntry(Base):
    __tablename__ = "giveaway_entries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    giveaway_id = Column(BigInteger, ForeignKey("giveaways.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint('giveaway_id', 'user_id', name='uq_giveaway_user'),
    )


