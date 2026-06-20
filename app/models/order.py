from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)

    # Fyers order fields
    fyers_order_id = Column(String(100), nullable=True, unique=True)
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(20), default="NSE")
    side = Column(String(10), nullable=False)          # BUY / SELL
    order_type = Column(String(20), default="MARKET")  # MARKET / LIMIT / SL / SL-M
    product_type = Column(String(20), default="INTRADAY")  # INTRADAY / CNC / CO / BO
    quantity = Column(Integer, nullable=False)
    price = Column(Float, default=0.0)
    stop_price = Column(Float, default=0.0)

    # Status
    status = Column(String(30), default="PENDING")
    filled_qty = Column(Integer, default=0)
    avg_fill_price = Column(Float, default=0.0)
    message = Column(Text, nullable=True)

    is_paper = Column(Integer, default=1)              # 0 = live, 1 = paper

    placed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="orders")
    strategy = relationship("Strategy", back_populates="orders")
