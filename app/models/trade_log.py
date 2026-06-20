from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


class TradeLog(Base):
    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)

    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)           # BUY / SELL
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)

    entry_time = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    exit_time = Column(DateTime, nullable=True)

    notes = Column(Text, nullable=True)
    is_paper = Column(Integer, default=1)

    user = relationship("User", back_populates="trade_logs")
    strategy = relationship("Strategy", back_populates="trade_logs")
