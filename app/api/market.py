"""
Market data routes: quotes, historical OHLCV, depth.
"""
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.fyers_client import get_fyers_client
from app.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/market", tags=["market"])

# Conservative chunk sizes (days) that Fyers reliably handles per request
_CHUNK_DAYS = {
    "1":   60,  "2":  60,  "3":  60,  "5":  60,
    "10":  80,  "15": 80,  "20": 80,  "30": 80,
    "60":  90,  "120": 90, "240": 90,
    "D":  365,   # 1 year per call
    "W":  180,   # ~6 months per call (safe)
    "M":  730,   # ~2 years per call  (safe)
}

_BREADTH_CACHE = {
    "data": None,
    "timestamp": 0
}


def _require_fyers():
    client = get_fyers_client()
    if client is None:
        raise HTTPException(
            status_code=403,
            detail="Fyers account not linked. Please authenticate first.",
        )
    return client


@router.get("/quote")
def get_quote(
    symbols: str = Query(..., description="Comma-separated Fyers symbols"),
    current_user: User = Depends(get_current_user),
):
    fyers = _require_fyers()
    response = fyers.quotes({"symbols": symbols})
    if response.get("s") != "ok":
        raise HTTPException(status_code=400, detail=response)
    return response


import yfinance as yf

@router.get("/turnover")
def get_turnover(
    symbol: str = Query(..., description="Fyers symbol (e.g., NSE:SBIN-EQ)"),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the turnover (Total Traded Value) and volume for a specific stock.
    """
    fyers = _require_fyers()
    response = fyers.quotes({"symbols": symbol})
    if response.get("s") != "ok":
        raise HTTPException(status_code=400, detail=response)
    
    data = response.get("d", [])
    if not data:
        raise HTTPException(status_code=404, detail="No data found for symbol")
        
    v_data = data[0].get("v", {})
    
    return {
        "symbol": symbol,
        "turnover": v_data.get("ttv", 0),
        "volume": v_data.get("volume", 0),
        "ltp": v_data.get("lp", 0)
    }


@router.get("/fundamentals")
def get_fundamentals(
    symbol: str = Query(..., description="Fyers symbol (e.g., NSE:SBIN-EQ)"),
    current_user: User = Depends(get_current_user),
):
    """
    Returns fundamental data for a specific stock using Yahoo Finance.
    """
    try:
        # Convert Fyers symbol to Yahoo Finance symbol
        # e.g., NSE:SBIN-EQ -> SBIN.NS
        parts = symbol.split(':')
        if len(parts) == 2:
            exchange = parts[0]
            ticker_part = parts[1].replace('-EQ', '').replace('-INDEX', '')
            if exchange == 'NSE':
                yf_symbol = f"{ticker_part}.NS"
            elif exchange == 'BSE':
                yf_symbol = f"{ticker_part}.BO"
            else:
                yf_symbol = ticker_part
        else:
            yf_symbol = symbol

        ticker = yf.Ticker(yf_symbol)
        info = ticker.info
        
        # Extract key fundamentals
        fundamentals = {
            "marketCap": info.get("marketCap", 0),
            "trailingPE": info.get("trailingPE", 0),
            "forwardPE": info.get("forwardPE", 0),
            "dividendYield": info.get("dividendYield", 0),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh", 0),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow", 0),
            "priceToBook": info.get("priceToBook", 0),
            "trailingEps": info.get("trailingEps", 0),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "shortName": info.get("shortName", yf_symbol)
        }
        return {"s": "ok", "fundamentals": fundamentals}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch fundamentals: {str(e)}")


@router.get("/history")
def get_history(
    symbol: str = Query(...),
    resolution: str = Query("D", description="1, 5, 15, 30, 60, D, W, M"),
    date_format: int = Query(0, description="0=unix, 1=YYYY-MM-DD"),
    range_from: str = Query(..., description="YYYY-MM-DD or unix timestamp"),
    range_to:   str = Query(..., description="YYYY-MM-DD or unix timestamp"),
    current_user: User = Depends(get_current_user),
):
    fyers = _require_fyers()
    data = {
        "symbol":      symbol,
        "resolution":  resolution,
        "date_format": date_format,
        "range_from":  range_from,
        "range_to":    range_to,
        "cont_flag":   "1",
    }
    response = fyers.history(data)
    if response.get("s") != "ok":
        msg = response.get("message") or response.get("errmsg") or str(response)
        raise HTTPException(status_code=400, detail=f"Fyers error: {msg}")
    return response


@router.get("/history/full")
def get_full_history(
    symbol:     str = Query(...),
    resolution: str = Query("M", description="1, 5, 15, 30, 60, D, W, M"),
    range_from: str = Query(..., description="YYYY-MM-DD  e.g. 2010-01-01"),
    range_to:   str = Query(..., description="YYYY-MM-DD  e.g. 2026-12-31"),
    current_user: User = Depends(get_current_user),
):
    """
    Splits a long date range into safe Fyers-sized chunks, fetches each,
    deduplicates and returns merged OHLCV candles. Partial data is returned
    even when some chunks fail (e.g. data not available for very old dates).
    """
    fyers = _require_fyers()

    chunk_days = _CHUNK_DAYS.get(resolution, 180)
    start_dt   = datetime.strptime(range_from, "%Y-%m-%d")
    end_dt     = datetime.strptime(range_to,   "%Y-%m-%d")

    all_candles: list = []
    seen_ts:     set  = set()
    chunk_errors: list = []

    cursor = start_dt
    while cursor <= end_dt:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end_dt)

        rf = int(cursor.timestamp())
        rt = int(chunk_end.timestamp())

        try:
            resp = fyers.history({
                "symbol":      symbol,
                "resolution":  resolution,
                "date_format": 0,        # unix — required by lightweight-charts
                "range_from":  rf,
                "range_to":    rt,
                "cont_flag":   "1",
            })

            if resp.get("s") == "ok":
                for candle in resp.get("candles") or []:
                    ts = candle[0]
                    if ts not in seen_ts:
                        seen_ts.add(ts)
                        all_candles.append(candle)
            else:
                msg = resp.get("message") or resp.get("errmsg") or "unknown error"
                chunk_errors.append(
                    f"{cursor.date()} → {chunk_end.date()}: {msg}"
                )
        except Exception as exc:
            chunk_errors.append(f"{cursor.date()} → {chunk_end.date()}: {exc}")

        cursor = chunk_end + timedelta(days=1)
        time.sleep(0.2)   # polite rate limit

    if not all_candles:
        detail = f"No data found for {symbol} ({resolution}) from {range_from} to {range_to}."
        if chunk_errors:
            detail += " Chunk errors: " + " | ".join(chunk_errors[:3])
        raise HTTPException(status_code=404, detail=detail)

    all_candles.sort(key=lambda c: c[0])
    return {
        "s":       "ok",
        "candles": all_candles,
        "total":   len(all_candles),
        "warnings": chunk_errors,   # front-end can log these
    }


@router.get("/depth")
def get_market_depth(
    symbol: str = Query(...),
    ohlcv_flag: int = Query(1),
    current_user: User = Depends(get_current_user),
):
    fyers = _require_fyers()
    data = {"symbol": symbol, "ohlcv_flag": ohlcv_flag}
    response = fyers.depth(data)
    if response.get("s") != "ok":
        raise HTTPException(status_code=400, detail=response)
    return response


@router.get("/search")
def search_symbols(
    q: str = Query(..., min_length=2),
    current_user: User = Depends(get_current_user),
):
    fyers = _require_fyers()
    response = fyers.symbol_master({"exchange": "NSE", "segment": "CM"})
    return response


@router.get("/analysis")
def get_stock_analysis(
    symbol: str = Query(..., description="Fyers symbol (e.g., NSE:RELIANCE-EQ)"),
    current_user: User = Depends(get_current_user),
):
    from app.api.ai_screener import _sma, _rsi
    from app.api.screener import _fetch_chunked_history, _resample_daily_to_weekly, _resample_daily_to_monthly
    import yfinance as yf
    
    fyers = _require_fyers()
    
    # 1. Fetch Fundamentals
    try:
        parts = symbol.split(':')
        if len(parts) == 2:
            exchange = parts[0]
            ticker_part = parts[1].replace('-EQ', '').replace('-INDEX', '')
            yf_symbol = f"{ticker_part}.NS" if exchange == 'NSE' else (f"{ticker_part}.BO" if exchange == 'BSE' else ticker_part)
        else:
            yf_symbol = symbol

        ticker = yf.Ticker(yf_symbol)
        info = ticker.info
        trailing_pe = info.get("trailingPE", 0)
        trailing_eps = info.get("trailingEps", 0)
        market_cap = info.get("marketCap", 0)
        
        if trailing_pe > 0 and trailing_pe < 40 and trailing_eps > 0:
            fund_status = "Good"
        elif trailing_pe >= 40 or trailing_eps < 0:
            fund_status = "Bad"
        else:
            fund_status = "Average"
    except Exception as e:
        fund_status = "Unknown"
        
    # 2. Fetch Technicals (D, W, M)
    today = datetime.today()
    start_dt = today - timedelta(days=5*365) # 5 years for enough monthly candles
    
    technicals = {"daily": "Unknown", "weekly": "Unknown", "monthly": "Unknown"}
    volume_profile = "Unknown"
    
    try:
        daily_candles, err = _fetch_chunked_history(fyers, symbol, "D", start_dt, today)
        if not err and daily_candles and len(daily_candles) > 50:
            weekly_candles = _resample_daily_to_weekly(daily_candles)
            monthly_candles = _resample_daily_to_monthly(daily_candles)
            
            def evaluate_tf(candles):
                if not candles or len(candles) < 50:
                    return "Unknown"
                closes = [c[4] for c in candles]
                curr_close = closes[-1]
                sma20 = _sma(closes, 20)
                sma50 = _sma(closes, 50)
                rsi14 = _rsi(closes, 14)
                
                if curr_close > sma20 and curr_close > sma50 and rsi14 > 60:
                    return "Very Good"
                elif curr_close > sma20 and rsi14 > 50:
                    return "Good"
                else:
                    return "Bad"
            
            technicals["daily"] = evaluate_tf(daily_candles)
            technicals["weekly"] = evaluate_tf(weekly_candles)
            technicals["monthly"] = evaluate_tf(monthly_candles)
            
            def is_volume_ascending(candles):
                if not candles or len(candles) < 20:
                    return False
                volumes = [c[5] for c in candles]
                sma5 = _sma(volumes, 5)
                sma20 = _sma(volumes, 20)
                return sma5 > sma20
                
            asc_count = 0
            if is_volume_ascending(daily_candles): asc_count += 1
            if is_volume_ascending(weekly_candles): asc_count += 1
            if is_volume_ascending(monthly_candles): asc_count += 1
            
            if asc_count == 3: volume_profile = "Very Good"
            elif asc_count == 2: volume_profile = "Good"
            elif asc_count == 1: volume_profile = "Bad"
            else: volume_profile = "Very Bad"
    except Exception as e:
        pass
        
    return {
        "symbol": symbol,
        "fundamentals": fund_status,
        "technicals": technicals,
        "volume_profile": volume_profile
    }


# Symbols shown in the live ticker bar
TICKER_SYMBOLS = [
    "NSE:NIFTY50-INDEX",
    "NSE:NIFTYBANK-INDEX",
    "NSE:RELIANCE-EQ",
    "NSE:TCS-EQ",
    "NSE:SBIN-EQ",
    "NSE:INFY-EQ",
    "NSE:HDFCBANK-EQ",
]

# Friendly display names
TICKER_DISPLAY = {
    "NSE:NIFTY50-INDEX":  "NIFTY",
    "NSE:NIFTYBANK-INDEX": "BANKNIFTY",
    "NSE:RELIANCE-EQ":    "RELIANCE",
    "NSE:TCS-EQ":         "TCS",
    "NSE:SBIN-EQ":        "SBIN",
    "NSE:INFY-EQ":        "INFY",
    "NSE:HDFCBANK-EQ":    "HDFCBANK",
}


@router.get("/ticker")
def get_ticker_quotes(
    current_user: User = Depends(get_current_user),
):
    """
    Returns live LTP and day-change% for the default ticker symbols.
    Called frequently by the frontend ticker bar (every ~5 s).
    """
    fyers = get_fyers_client()
    if fyers is None:
        # Return empty list gracefully — ticker will show stale / no data
        return {"s": "ok", "quotes": []}

    symbols_str = ",".join(TICKER_SYMBOLS)
    resp = fyers.quotes({"symbols": symbols_str})

    quotes = []
    if resp.get("s") == "ok":
        for item in resp.get("d") or []:
            sym = item.get("n", "")
            v   = item.get("v") or {}
            ltp = v.get("lp", 0)
            chg = v.get("ch", 0)       # absolute change
            chg_pct = v.get("chp", 0)  # % change
            quotes.append({
                "symbol":  TICKER_DISPLAY.get(sym, sym.split(":")[-1].replace("-EQ", "").replace("-INDEX", "")),
                "ltp":     round(ltp, 2),
                "change":  round(chg, 2),
                "chg_pct": round(chg_pct, 2),
                "up":      chg >= 0,
            })

    return {"s": "ok", "quotes": quotes}


@router.get("/breadth")
def get_market_breadth(
    days: int = Query(60, description="Number of days to plot"),
    current_user: User = Depends(get_current_user),
):
    from app.api.screener import NIFTY50_SYMBOLS, _fetch_chunked_history
    import pandas as pd
    import ta
    
    # Simple 1-hour TTL cache
    if _BREADTH_CACHE["data"] and (time.time() - _BREADTH_CACHE["timestamp"] < 3600):
        cached_data = _BREADTH_CACHE["data"]
        return {"s": "ok", "data": cached_data[-days:] if days < len(cached_data) else cached_data}

    fyers = _require_fyers()
    
    today = datetime.today()
    start_dt = today - timedelta(days=365)
    
    daily_metrics = {}

    for sym in NIFTY50_SYMBOLS:
        try:
            candles, err = _fetch_chunked_history(fyers, sym, "D", start_dt, today)
            if err or not candles:
                continue
            
            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['ema50'] = ta.trend.ema_indicator(df['close'], window=50)
            df['ema200'] = ta.trend.ema_indicator(df['close'], window=200)
            
            for i in range(1, len(df)):
                row = df.iloc[i]
                prev_row = df.iloc[i-1]
                ts = int(row['timestamp'])
                close = row['close']
                prev_close = prev_row['close']
                vol = row['volume']
                
                if ts not in daily_metrics:
                    dt_str = datetime.fromtimestamp(ts).strftime('%m/%d')
                    daily_metrics[ts] = {
                        "date": dt_str,
                        "timestamp": ts,
                        "advance": 0,
                        "decline": 0,
                        "pos_vol": 0,
                        "neg_vol": 0,
                        "above_50ema": 0,
                        "above_200ema": 0
                    }
                
                if close > prev_close:
                    daily_metrics[ts]["advance"] += 1
                    daily_metrics[ts]["pos_vol"] += vol
                elif close < prev_close:
                    daily_metrics[ts]["decline"] += 1
                    daily_metrics[ts]["neg_vol"] += vol
                    
                if not pd.isna(row['ema50']) and close > row['ema50']:
                    daily_metrics[ts]["above_50ema"] += 1
                if not pd.isna(row['ema200']) and close > row['ema200']:
                    daily_metrics[ts]["above_200ema"] += 1
        except Exception:
            pass
            
    # Convert dict to sorted list
    sorted_metrics = [daily_metrics[ts] for ts in sorted(daily_metrics.keys())]
    
    # Cache the last 100 days to be safe
    final_data = sorted_metrics[-100:]
    
    _BREADTH_CACHE["data"] = final_data
    _BREADTH_CACHE["timestamp"] = time.time()
    
    return {"s": "ok", "data": final_data[-days:] if days < len(final_data) else final_data}
