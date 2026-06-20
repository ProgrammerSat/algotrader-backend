from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    symbol: str
    exchange: str = "NSE"
    timeframe: str = "5"
    strategy_type: str = "EMA_CROSSOVER"
    params_json: str = "{}"
    quantity: int = 1
    max_loss_per_trade: Optional[float] = None
    target_pnl: Optional[float] = None
    stop_loss_pct: float = 1.0
    take_profit_pct: float = 2.0
    trade_start_time: str = "09:15"
    trade_end_time: str = "15:15"
    is_paper_trading: bool = True


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    timeframe: Optional[str] = None
    strategy_type: Optional[str] = None
    params_json: Optional[str] = None
    quantity: Optional[int] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    trade_start_time: Optional[str] = None
    trade_end_time: Optional[str] = None
    is_paper_trading: Optional[bool] = None


class StrategyOut(BaseModel):
    id: int
    name: str
    symbol: str
    exchange: str
    timeframe: str
    strategy_type: str
    params_json: str
    quantity: int
    stop_loss_pct: float
    take_profit_pct: float
    trade_start_time: str
    trade_end_time: str
    status: str
    is_paper_trading: bool
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
