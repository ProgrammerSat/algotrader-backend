from pydantic import BaseModel
from typing import Optional


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
