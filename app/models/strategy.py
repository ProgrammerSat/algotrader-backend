from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base
import enum


class StrategyStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    BACKTESTING = "backtesting"


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    symbol = Column(String(50), nullable=False)          # e.g. NSE:NIFTY50-INDEX
    exchange = Column(String(20), default="NSE")
    timeframe = Column(String(10), default="5")          # in minutes

    # Strategy type
    strategy_type = Column(String(50), default="EMA_CROSSOVER")

    # Parameters (JSON encoded)
    params_json = Column(Text, default="{}")

    # Risk management
    quantity = Column(Integer, default=1)
    max_loss_per_trade = Column(Float, nullable=True)
    target_pnl = Column(Float, nullable=True)
    stop_loss_pct = Column(Float, default=1.0)          # %
    take_profit_pct = Column(Float, default=2.0)         # %

    # Scheduling
    trade_start_time = Column(String(10), default="09:15")
    trade_end_time = Column(String(10), default="15:15")

    status = Column(String(20), default=StrategyStatus.STOPPED)
    is_paper_trading = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="strategies")
    orders = relationship("Order", back_populates="strategy", cascade="all, delete-orphan")
    trade_logs = relationship("TradeLog", back_populates="strategy", cascade="all, delete-orphan")
