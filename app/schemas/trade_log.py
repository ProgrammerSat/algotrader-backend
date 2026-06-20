from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TradeLogCreate(BaseModel):
    symbol: str
    side: str
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    notes: Optional[str] = None
    is_paper: int = 1
    strategy_id: Optional[int] = None


class TradeLogOut(BaseModel):
    id: int
    symbol: str
    side: str
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    entry_time: datetime
    exit_time: Optional[datetime] = None
    is_paper: int
    strategy_id: Optional[int] = None

    class Config:
        from_attributes = True


class WatchlistCreate(BaseModel):
    name: str


class WatchlistSymbolOut(BaseModel):
    id: int
    symbol: str
    exchange: str

    class Config:
        from_attributes = True


class WatchlistOut(BaseModel):
    id: int
    name: str
    symbols: list[WatchlistSymbolOut] = []

    class Config:
        from_attributes = True


class AddSymbolRequest(BaseModel):
    symbol: str
    exchange: str = "NSE"
