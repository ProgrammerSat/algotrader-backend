from sqlalchemy import Column, Integer, String, Float, Date
from app.core.database import Base

class WMMarketSpread(Base):
    __tablename__ = "wm_market_spread"

    WMDate = Column(Date, primary_key=True, index=True)
    WMStocksAdvToYesterday = Column(Integer, nullable=True)
    WMStocksDecToYesterday = Column(Integer, nullable=True)
    WMStocksAdvFrmOpenToday = Column(Integer, nullable=True)
    WMStocksDecFrmOpenToday = Column(Integer, nullable=True)
    WMStockBullVolYesterday = Column(Float, nullable=True)
    WMStockBearVolYesterday = Column(Float, nullable=True)
    WMStockBullVolToday = Column(Float, nullable=True)
    WMStockBearVolToday = Column(Float, nullable=True)
    WMTrinYesterday = Column(Float, nullable=True)
    WMTrinToday = Column(Float, nullable=True)
    WMStocksAbove200EMA = Column(Integer, nullable=True)
    WMStocksAbove50EMA = Column(Integer, nullable=True)


class WMIndexSentimentAnalysis(Base):
    __tablename__ = "wm_index_sentiment_analysis"

    WMDate = Column(String, primary_key=True, index=True)
    WMIndexName = Column(String(100), primary_key=True, index=True)
    WMIndexType = Column(String(50), nullable=True)
    WMIndexPosition = Column(String(50), nullable=True)
    WMIndexPositiontoNifty = Column(String(50), nullable=True)
    WMIndexWSMA30Position = Column(String(50), nullable=True)
    WMIndexCurrentPosition = Column(String(50), nullable=True)


class WMReference(Base):
    __tablename__ = "wm_reference"

    WMRefType = Column(String(50), primary_key=True, index=True)
    WMRefCode = Column(String(50), primary_key=True, index=True)
    WMRefShortName = Column(String(100), nullable=True)
    WMRefFullName = Column(String(255), nullable=True)
