from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class OrderCreate(BaseModel):
    symbol: str
    exchange: str = "NSE"
    side: str  # BUY / SELL
    order_type: str = "MARKET"
    product_type: str = "INTRADAY"
    quantity: int
    price: float = 0.0
    stop_price: float = 0.0
    is_paper: int = 1
    strategy_id: Optional[int] = None


class OrderOut(BaseModel):
    id: int
    symbol: str
    side: str
    order_type: str
    product_type: str
    quantity: int
    price: float
    stop_price: float
    status: str
    filled_qty: int
    avg_fill_price: float
    is_paper: int
    fyers_order_id: Optional[str] = None
    placed_at: datetime

    class Config:
        from_attributes = True
