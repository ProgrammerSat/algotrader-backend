"""
Screener routes: run pre-built market screening strategies.
"""
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Any, Union
from pydantic import BaseModel
import pandas as pd
import ta
import numpy as np

from app.core.fyers_client import get_fyers_client
from app.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/screener", tags=["screener"])

# Default Nifty 50 universe in Fyers symbol format
NIFTY50_SYMBOLS = [
    "NSE:RELIANCE-EQ", "NSE:TCS-EQ",       "NSE:HDFCBANK-EQ",  "NSE:INFY-EQ",
    "NSE:ICICIBANK-EQ","NSE:HINDUNILVR-EQ", "NSE:ITC-EQ",       "NSE:SBIN-EQ",
    "NSE:BHARTIARTL-EQ","NSE:KOTAKBANK-EQ", "NSE:LT-EQ",        "NSE:AXISBANK-EQ",
    "NSE:HCLTECH-EQ",  "NSE:WIPRO-EQ",     "NSE:ASIANPAINT-EQ","NSE:BAJFINANCE-EQ",
    "NSE:MARUTI-EQ",   "NSE:TITAN-EQ",     "NSE:ULTRACEMCO-EQ","NSE:NESTLEIND-EQ",
    "NSE:POWERGRID-EQ","NSE:NTPC-EQ",      "NSE:SUNPHARMA-EQ", "NSE:ONGC-EQ",
    "NSE:JSWSTEEL-EQ", "NSE:TATAMOTORS-EQ","NSE:TECHM-EQ",     "NSE:ADANIENT-EQ",
    "NSE:ADANIPORTS-EQ","NSE:COALINDIA-EQ", "NSE:BAJAJFINSV-EQ","NSE:DIVISLAB-EQ",
    "NSE:DRREDDY-EQ",  "NSE:EICHERMOT-EQ", "NSE:GRASIM-EQ",    "NSE:HEROMOTOCO-EQ",
    "NSE:HINDALCO-EQ", "NSE:INDUSINDBK-EQ","NSE:M&M-EQ",       "NSE:CIPLA-EQ",
    "NSE:BPCL-EQ",     "NSE:BRITANNIA-EQ", "NSE:TATACONSUM-EQ","NSE:SBILIFE-EQ",
    "NSE:HDFCLIFE-EQ", "NSE:TATASTEEL-EQ", "NSE:UPL-EQ",       "NSE:APOLLOHOSP-EQ",
    "NSE:BAJAJ-AUTO-EQ","NSE:TATAPOWER-EQ",
]

# User's requested watchlist
USER_WATCHLIST = [
    "NSE:GOPAL-EQ", "NSE:ACE-EQ", "NSE:SBIN-EQ", 
    "NSE:LINCOLN-EQ", "NSE:SUPRIYA-EQ", "NSE:TATATECH-EQ"
]


def _get_last_two_monthly_candles(fyers, symbol: str):
    """
    Fetch several months of Monthly OHLCV for `symbol`.
    Returns (prev_candle, curr_candle, error_msg).
    """
    today    = datetime.today()
    # 180 days to ensure we get at least 3-4 monthly candles
    rf       = int((today - timedelta(days=180)).timestamp())
    rt       = int(today.timestamp())

    resp = fyers.history({
        "symbol":      symbol,
        "resolution":  "M",
        "date_format": 0,
        "range_from":  rf,
        "range_to":    rt,
        "cont_flag":   "1",
    })

    if resp.get("s") != "ok":
        return None, None, resp.get("message") or resp.get("errmsg") or "Fyers error"

    candles = resp.get("candles") or []
    if len(candles) < 2:
        return None, None, f"Insufficient candles: found {len(candles)}"

    # Sort by timestamp ascending and take last two
    candles.sort(key=lambda c: c[0])
    return candles[-2], candles[-1], None


@router.get("/volume-surge")
def volume_surge_screener(
    threshold: float = Query(0.60, description="Min ratio: curr_vol / prev_vol (default 0.60 = 60%)"),
    only_bullish: bool = Query(False, description="Only include stocks where current close > previous close"),
    symbols:   str   = Query(None,  description="Comma-separated symbols. Leave blank for Nifty 50."),
    current_user: User = Depends(get_current_user),
):
    """
    Monthly Volume Surge Screener.
    """
    fyers = get_fyers_client()
    if not fyers:
        raise HTTPException(status_code=403, detail="Fyers account not linked.")

    universe = (
        [s.strip() for s in symbols.split(",") if s.strip()]
        if symbols else NIFTY50_SYMBOLS
    )

    results  = []
    skipped_details = []

    print(f"🚀 Screener Scan: {len(universe)} symbols | Threshold: {threshold} | Bullish: {only_bullish}")

    for sym in universe:
        try:
            prev, curr, err = _get_last_two_monthly_candles(fyers, sym)
            time.sleep(0.1)   # rate limit

            if err:
                print(f"⚠️  {sym}: {err}")
                skipped_details.append({"symbol": sym, "reason": err})
                continue

            prev_vol  = prev[5]
            curr_vol  = curr[5]
            prev_close = prev[4]
            curr_close = curr[4]

            if prev_vol == 0:
                skipped_details.append({"symbol": sym, "reason": "Prev volume is 0"})
                continue

            ratio = curr_vol / prev_vol
            
            # Check volume threshold
            if ratio < threshold:
                continue
                
            # Check bullish condition
            if only_bullish and curr_close <= prev_close:
                continue

            pct_chg = ((curr_close - prev_close) / prev_close * 100) if prev_close else 0
            results.append({
                "symbol":        sym,
                "curr_vol":      curr_vol,
                "prev_vol":      prev_vol,
                "vol_ratio":     round(ratio, 4),
                "vol_surge_pct": round((ratio - 1) * 100, 2),
                "curr_close":    curr_close,
                "prev_close":    prev_close,
                "price_chg_pct": round(pct_chg, 2),
                "curr_high":     curr[2],
                "curr_low":      curr[3],
                "curr_open":     curr[1],
            })
        except Exception as e:
            skipped_details.append({"symbol": sym, "reason": str(e)})

    results.sort(key=lambda r: r["vol_ratio"], reverse=True)
    print(f"✅ Scan complete. Matched: {len(results)}, Skipped: {len(skipped_details)}")

    return {
        "screener":  "Monthly Volume Surge",
        "threshold": threshold,
        "only_bullish": only_bullish,
        "scanned":   len(universe),
        "matched":   len(results),
        "skipped":   len(skipped_details),
        "skipped_details": skipped_details,
        "results":   results,
    }


def _calculate_sma(candles: list, period: int):
    """Calculates Simple Moving Average of closing prices."""
    if len(candles) < period:
        return None
    # candles format: [timestamp, open, high, low, close, volume]
    closes = [c[4] for c in candles[-period:]]
    return sum(closes) / period

def _fetch_chunked_history(fyers, symbol: str, resolution: str, start_dt: datetime, end_dt: datetime):
    """
    Fetches history in chunks to bypass Fyers API date range limits.
    """
    # Fyers API allows 365 days for D and 3650 for M.
    # Using optimal chunk sizes drastically reduces API calls to avoid rate limits (200/min).
    chunk_days = {
        "D": 365,
        "W": 365,
        "M": 3650,
    }.get(resolution, 100)

    all_candles = []
    seen_ts = set()
    cursor = start_dt

    while cursor <= end_dt:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end_dt)
        rf = int(cursor.timestamp())
        rt = int(chunk_end.timestamp())

        resp = fyers.history({
            "symbol":      symbol,
            "resolution":  resolution,
            "date_format": 0,
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
        elif resp.get("s") == "no_data":
            # Ignore empty chunks (e.g. weekends or today before market open)
            pass
        else:
            # If a chunk fails, we just return the error string to be handled by caller
            msg = resp.get("message") or resp.get("errmsg") or "Fyers error"
            return None, msg

        cursor = chunk_end + timedelta(days=1)
        time.sleep(0.1)

    all_candles.sort(key=lambda c: c[0])
    return all_candles, None

def _resample_daily_to_weekly(daily_candles: list) -> list:
    """Groups daily candles into weekly candles."""
    if not daily_candles:
        return []
    
    weekly_candles = []
    current_week = None
    
    week_ts = week_o = week_h = week_l = week_c = week_v = 0
    
    for c in daily_candles:
        ts, o, h, l, close, v = c
        dt = datetime.fromtimestamp(ts)
        year, week, _ = dt.isocalendar()
        week_key = (year, week)
        
        if current_week != week_key:
            if current_week is not None:
                weekly_candles.append([week_ts, week_o, week_h, week_l, week_c, week_v])
            current_week = week_key
            week_ts = ts
            week_o = o
            week_h = h
            week_l = l
            week_c = close
            week_v = v
        else:
            week_h = max(week_h, h)
            week_l = min(week_l, l)
            week_c = close  # last close of the week
            week_v += v     # sum of volume
            
    if current_week is not None:
        weekly_candles.append([week_ts, week_o, week_h, week_l, week_c, week_v])
        
    return weekly_candles

def _resample_daily_to_monthly(daily_candles: list) -> list:
    """Groups daily candles into monthly candles."""
    if not daily_candles:
        return []
    
    monthly_candles = []
    current_month = None
    
    month_ts = month_o = month_h = month_l = month_c = month_v = 0
    
    for c in daily_candles:
        ts, o, h, l, close, v = c
        dt = datetime.fromtimestamp(ts)
        month_key = (dt.year, dt.month)
        
        if current_month != month_key:
            if current_month is not None:
                monthly_candles.append([month_ts, month_o, month_h, month_l, month_c, month_v])
            current_month = month_key
            month_ts = ts
            month_o = o
            month_h = h
            month_l = l
            month_c = close
            month_v = v
        else:
            month_h = max(month_h, h)
            month_l = min(month_l, l)
            month_c = close  # last close of the month
            month_v += v     # sum of volume
            
    if current_month is not None:
        monthly_candles.append([month_ts, month_o, month_h, month_l, month_c, month_v])
        
    return monthly_candles

@router.get("/bottom-range")
def weekly_low_screener(
    weekly_change_threshold: float = Query(5.0, description="Max absolute weekly % change (default 5%)"),
    bottom_threshold: float = Query(15.0, description="Max % distance from 52-week low (default 15%)"),
    symbols: str = Query(None, description="Comma-separated symbols. Leave blank for Nifty 50."),
    current_user: User = Depends(get_current_user),
):
    """
    Identifies stocks that are:
    1. Weekly price change within ±weekly_change_threshold% (flat/low-volatility week).
    2. Near their 52-week low (within bottom_threshold%).

    Uses Weekly ('W') candles. Needs at least 53 weekly candles (~1 year + 1 week).
    """
    fyers = get_fyers_client()
    if not fyers:
        raise HTTPException(status_code=403, detail="Fyers account not linked.")

    universe = (
        [s.strip() for s in symbols.split(",") if s.strip()]
        if symbols else NIFTY50_SYMBOLS
    )

    results = []
    skipped_details = []

    today = datetime.today()
    # Fetch enough days to comfortably cover 53 weekly candles + buffer
    # 60 weeks = 420 days
    start_dt = today - timedelta(days=60 * 7)
    end_dt = today

    print(f"🚀 Weekly Low Scan: {len(universe)} symbols | Weekly Chg ≤ {weekly_change_threshold}% | Bottom ≤ {bottom_threshold}%")

    for sym in universe:
        try:
            # Fetch Daily candles and resample to avoid Fyers Weekly API bugs
            daily_candles, err = _fetch_chunked_history(fyers, sym, "D", start_dt, end_dt)

            if err:
                skipped_details.append({"symbol": sym, "reason": err})
                continue
            if not daily_candles:
                skipped_details.append({"symbol": sym, "reason": "No data returned"})
                continue
            
            candles = _resample_daily_to_weekly(daily_candles)

            if len(candles) < 53:
                skipped_details.append({
                    "symbol": sym,
                    "reason": f"Insufficient history: {len(candles)} weekly candles (need 53)"
                })
                continue

            # candles format: [timestamp, open, high, low, close, volume]
            curr  = candles[-1]
            prev  = candles[-2]

            curr_close = curr[4]
            prev_close = prev[4]

            if prev_close == 0:
                skipped_details.append({"symbol": sym, "reason": "Previous close is 0"})
                continue

            # 1. Weekly % change
            weekly_chg_pct = ((curr_close - prev_close) / prev_close) * 100
            if abs(weekly_chg_pct) > weekly_change_threshold:
                continue

            # 2. Near 52-week low
            last_52_weeks = candles[-52:]
            min_52w_low   = min(c[3] for c in last_52_weeks)

            dist_from_low = ((curr_close - min_52w_low) / min_52w_low) * 100
            if dist_from_low > bottom_threshold:
                continue

            results.append({
                "symbol":            sym,
                "curr_close":        round(curr_close, 2),
                "prev_close":        round(prev_close, 2),
                "weekly_chg_pct":    round(weekly_chg_pct, 2),
                "curr_high":         round(curr[2], 2),
                "curr_low":          round(curr[3], 2),
                "min_52w_low":       round(min_52w_low, 2),
                "dist_from_low_pct": round(dist_from_low, 2),
            })

        except Exception as e:
            skipped_details.append({"symbol": sym, "reason": str(e)})

    # Sort by closest to 52-week low first
    results.sort(key=lambda x: x["dist_from_low_pct"])

    return {
        "screener":                "Weekly Low",
        "weekly_change_threshold": weekly_change_threshold,
        "bottom_threshold":        bottom_threshold,
        "scanned":                 len(universe),
        "matched":                 len(results),
        "results":                 results,
        "skipped":                 len(skipped_details),
        "skipped_details":         skipped_details,
    }


@router.get("/weekly-sma-support")
def weekly_sma_support_screener(
    sma_period: int = Query(30, description="SMA period (default 30)"),
    vol_threshold: float = Query(0.60, description="Min ratio: curr_vol / prev_vol (default 0.60)"),
    proximity_pct: float = Query(1.0, description="Max % distance between Low and SMA for 'support' condition"),
    symbols: str = Query(None, description="Comma-separated symbols. Leave blank for Nifty 50."),
    current_user: User = Depends(get_current_user),
):
    """
    Weekly SMA Support Screener.
    Checks if Weekly Low is >= SMA(period) or within proximity_pct.
    Also checks if Current Weekly Volume >= vol_threshold * Previous Weekly Volume.
    """
    fyers = get_fyers_client()
    if not fyers:
        raise HTTPException(status_code=403, detail="Fyers account not linked.")

    universe = (
        [s.strip() for s in symbols.split(",") if s.strip()]
        if symbols else NIFTY50_SYMBOLS
    )

    results = []
    skipped_details = []

    print(f"🚀 Weekly SMA Scan: {len(universe)} symbols | SMA: {sma_period} | Vol: {vol_threshold}")

    # We need at least `sma_period + 1` weekly candles.
    # Calculate days to fetch dynamically so it supports any SMA period (e.g., up to 200).
    weeks_to_fetch = sma_period + 20  # Add 20 weeks buffer for holidays
    days_to_fetch = weeks_to_fetch * 7
    
    today = datetime.today()
    start_dt = today - timedelta(days=days_to_fetch)
    end_dt = today

    for sym in universe:
        try:
            # Fetch Daily candles and resample to avoid Fyers Weekly API bugs
            daily_candles, err = _fetch_chunked_history(fyers, sym, "D", start_dt, end_dt)

            if err:
                skipped_details.append({"symbol": sym, "reason": err})
                continue
            if not daily_candles:
                skipped_details.append({"symbol": sym, "reason": "No data returned"})
                continue
            
            candles = _resample_daily_to_weekly(daily_candles)

            if len(candles) < sma_period + 1:
                skipped_details.append({"symbol": sym, "reason": f"Insufficient candles ({len(candles)})"})
                continue

            curr = candles[-1]
            prev = candles[-2]
            
            # Calculate SMA 30 (on previous candles to avoid current week bias, or including current?)
            # Usually traders use the SMA value *at* the current candle.
            sma_val = _calculate_sma(candles, sma_period)
            
            curr_low = curr[3]
            curr_vol = curr[5]
            prev_vol = prev[5]
            
            if not sma_val or prev_vol == 0:
                continue

            # 1. Volume Condition: Current Vol >= 60% of Prev Vol
            vol_ratio = curr_vol / prev_vol
            if vol_ratio < vol_threshold:
                continue

            # 2. SMA Support Condition: Low should be near SMA
            # "Greater than or close to" with a hard cap of 1%
            diff_pct = ((curr_low - sma_val) / sma_val) * 100
            
            # Use the user's proximity but cap it at 1.0%
            effective_proximity = min(abs(proximity_pct), 1.0)
            
            # The distance (whether above or below) must not exceed the limit
            if abs(diff_pct) > effective_proximity:
                continue

            results.append({
                "symbol":        sym,
                "curr_low":      curr_low,
                "sma_val":       round(sma_val, 2),
                "dist_pct":      round(diff_pct, 2),
                "vol_ratio":     round(vol_ratio, 4),
                "curr_vol":      curr_vol,
                "prev_vol":      prev_vol,
                "curr_close":    curr[4],
                "prev_close":    prev[4],
            })
        except Exception as e:
            skipped_details.append({"symbol": sym, "reason": str(e)})

    results.sort(key=lambda r: r["dist_pct"]) # Sort by proximity to SMA
    return {
        "screener": "Weekly SMA Support",
        "sma_period": sma_period,
        "vol_threshold": vol_threshold,
        "scanned": len(universe),
        "matched": len(results),
        "results": results,
        "skipped": len(skipped_details),
        "skipped_details": skipped_details,
    }


@router.get("/weekly-volume-close")
def weekly_volume_close_screener(
    vol_surge_pct: float = Query(60.0, description="Min % by which current weekly volume must exceed previous (default 60%)"),
    symbols: str = Query(None, description="Comma-separated symbols. Leave blank for Nifty 50."),
    current_user: User = Depends(get_current_user),
):
    """
    Weekly Volume & Close Screener.

    Selects stocks where:
      1. Current Weekly Volume > Previous Weekly Volume by at least vol_surge_pct%
         (i.e. curr_vol / prev_vol >= 1 + vol_surge_pct/100)
      2. Current Weekly Close >= Previous Weekly Close
    """
    fyers = get_fyers_client()
    if not fyers:
        raise HTTPException(status_code=403, detail="Fyers account not linked.")

    universe = (
        [s.strip() for s in symbols.split(",") if s.strip()]
        if symbols else NIFTY50_SYMBOLS
    )

    results = []
    skipped_details = []

    # Fetch last ~10 weeks of weekly candles (need only 2, but buffer for safety)
    today = datetime.today()
    rf = int((today - timedelta(days=14 * 7)).timestamp())
    rt = int(today.timestamp())

    vol_ratio_threshold = 1.0 + (vol_surge_pct / 100.0)

    print(f"🚀 Weekly Vol+Close Scan: {len(universe)} symbols | Vol Surge ≥ {vol_surge_pct}% | Close ≥ Prev Close")

    for sym in universe:
        try:
            resp = fyers.history({
                "symbol":      sym,
                "resolution":  "W",
                "date_format": 0,
                "range_from":  rf,
                "range_to":    rt,
                "cont_flag":   "1",
            })
            time.sleep(0.1)  # Rate limit

            if resp.get("s") != "ok":
                skipped_details.append({"symbol": sym, "reason": resp.get("message") or "Fyers error"})
                continue

            candles = resp.get("candles") or []
            if len(candles) < 2:
                skipped_details.append({
                    "symbol": sym,
                    "reason": f"Insufficient candles: {len(candles)} (need 2)"
                })
                continue

            # candles format: [timestamp, open, high, low, close, volume]
            candles.sort(key=lambda c: c[0])
            curr = candles[-1]
            prev = candles[-2]

            curr_close = curr[4]
            prev_close = prev[4]
            curr_vol   = curr[5]
            prev_vol   = prev[5]

            if prev_vol == 0:
                skipped_details.append({"symbol": sym, "reason": "Previous volume is 0"})
                continue

            if prev_close == 0:
                skipped_details.append({"symbol": sym, "reason": "Previous close is 0"})
                continue

            vol_ratio = curr_vol / prev_vol

            # Condition 1: volume surge ≥ threshold
            if vol_ratio < vol_ratio_threshold:
                continue

            # Condition 2: close >= previous close
            if curr_close < prev_close:
                continue

            price_chg_pct = ((curr_close - prev_close) / prev_close) * 100

            results.append({
                "symbol":        sym,
                "curr_close":    round(curr_close, 2),
                "prev_close":    round(prev_close, 2),
                "price_chg_pct": round(price_chg_pct, 2),
                "curr_vol":      curr_vol,
                "prev_vol":      prev_vol,
                "vol_ratio":     round(vol_ratio, 4),
                "vol_surge_pct": round((vol_ratio - 1) * 100, 2),
                "curr_high":     round(curr[2], 2),
                "curr_low":      round(curr[3], 2),
                "curr_open":     round(curr[1], 2),
            })

        except Exception as e:
            skipped_details.append({"symbol": sym, "reason": str(e)})

    # Sort by highest volume ratio first
    results.sort(key=lambda r: r["vol_ratio"], reverse=True)

    print(f"✅ Scan complete. Matched: {len(results)}, Skipped: {len(skipped_details)}")

    return {
        "screener":      "Weekly Volume & Close",
        "vol_surge_pct": vol_surge_pct,
        "scanned":       len(universe),
        "matched":       len(results),
        "results":       results,
        "skipped":       len(skipped_details),
        "skipped_details": skipped_details,
    }


# ── Custom Strategy Builder Models ──────────────────────────────────────────────

class IndicatorDef(BaseModel):
    name: str # 'Close', 'SMA', 'EMA', 'RSI', 'Value'
    period: Optional[int] = None
    value: Optional[float] = None # Used if name == 'Value'

class StrategyCondition(BaseModel):
    ind1: IndicatorDef
    operator: str # '>', '<', 'crosses_above', 'crosses_below', '=='
    ind2: IndicatorDef

class CustomStrategyRequest(BaseModel):
    timeframe: str = "D" # 'D', 'W', 'M'
    symbols: Optional[str] = None
    conditions: List[StrategyCondition]

def _calculate_indicator(df: pd.DataFrame, ind: IndicatorDef) -> pd.Series:
    if ind.name == 'Close':
        return df['close']
    elif ind.name == 'SMA' and ind.period:
        return ta.trend.sma_indicator(df['close'], window=ind.period)
    elif ind.name == 'EMA' and ind.period:
        return ta.trend.ema_indicator(df['close'], window=ind.period)
    elif ind.name == 'RSI' and ind.period:
        return ta.momentum.rsi(df['close'], window=ind.period)
    elif ind.name == 'Value' and ind.value is not None:
        return pd.Series(ind.value, index=df.index)
    return pd.Series(np.nan, index=df.index)

@router.post("/custom")
def custom_screener(
    req: CustomStrategyRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Custom Screener endpoint allowing dynamic conditions.
    """
    fyers = get_fyers_client()
    if not fyers:
        raise HTTPException(status_code=403, detail="Fyers account not linked.")

    universe = (
        [s.strip() for s in req.symbols.split(",") if s.strip()]
        if req.symbols else NIFTY50_SYMBOLS
    )

    results = []
    skipped_details = []

    # Figure out the max lookback needed based on the conditions
    max_period = 1
    for cond in req.conditions:
        if cond.ind1.period and cond.ind1.period > max_period:
            max_period = cond.ind1.period
        if cond.ind2.period and cond.ind2.period > max_period:
            max_period = cond.ind2.period
            
    # Add buffer for ta calculations (e.g., EMA needs more data to stabilize)
    lookback = max_period + 50
    if req.timeframe == 'W':
        days_to_fetch = lookback * 7
    elif req.timeframe == 'M':
        days_to_fetch = lookback * 31
    else:
        days_to_fetch = lookback * 2 # weekends buffer
        
    start_dt = datetime.today() - timedelta(days=days_to_fetch)
    end_dt = datetime.today()
    
    print(f"🚀 Custom Strategy Scan: {len(universe)} symbols | TF: {req.timeframe} | Conditions: {len(req.conditions)}")

    for sym in universe:
        try:
            # 1. Fetch data
            daily_candles, err = _fetch_chunked_history(fyers, sym, "D", start_dt, end_dt)
            if err:
                skipped_details.append({"symbol": sym, "reason": err})
                continue
            if not daily_candles:
                skipped_details.append({"symbol": sym, "reason": "No data returned"})
                continue
                
            # 2. Resample if necessary
            if req.timeframe == 'W':
                candles = _resample_daily_to_weekly(daily_candles)
            elif req.timeframe == 'M':
                candles = _resample_daily_to_monthly(daily_candles)
            else:
                candles = daily_candles
                
            if len(candles) < max_period + 1:
                 skipped_details.append({"symbol": sym, "reason": f"Insufficient candles ({len(candles)}) for max period {max_period}"})
                 continue
                 
            # 3. Create DataFrame
            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 4. Evaluate Conditions
            all_conditions_met = True
            
            # We want to keep track of the latest calculated values for returning them
            latest_values = {}
            
            for i, cond in enumerate(req.conditions):
                s1 = _calculate_indicator(df, cond.ind1)
                s2 = _calculate_indicator(df, cond.ind2)
                
                # Save latest values for returning to frontend
                val1 = s1.iloc[-1]
                val2 = s2.iloc[-1]
                
                # Naming for UI
                name1 = f"{cond.ind1.name}({cond.ind1.period})" if cond.ind1.period else cond.ind1.name
                name2 = f"{cond.ind2.name}({cond.ind2.period})" if cond.ind2.period else (str(cond.ind2.value) if cond.ind2.value is not None else cond.ind2.name)
                
                latest_values[f"cond_{i}_ind1"] = {"name": name1, "value": round(float(val1), 2) if not pd.isna(val1) else None}
                latest_values[f"cond_{i}_ind2"] = {"name": name2, "value": round(float(val2), 2) if not pd.isna(val2) else None}
                
                if cond.operator == '>':
                    match = s1.iloc[-1] > s2.iloc[-1]
                elif cond.operator == '<':
                    match = s1.iloc[-1] < s2.iloc[-1]
                elif cond.operator == '==':
                    match = s1.iloc[-1] == s2.iloc[-1]
                elif cond.operator == 'crosses_above':
                    match = (s1.iloc[-2] <= s2.iloc[-2]) and (s1.iloc[-1] > s2.iloc[-1])
                elif cond.operator == 'crosses_below':
                    match = (s1.iloc[-2] >= s2.iloc[-2]) and (s1.iloc[-1] < s2.iloc[-1])
                else:
                    match = False
                    
                if not match:
                    all_conditions_met = False
                    break # Stop evaluating further conditions if one fails
                    
            if all_conditions_met:
                last_candle = df.iloc[-1]
                prev_candle = df.iloc[-2]
                if prev_candle['close'] != 0:
                    price_chg_pct = ((last_candle['close'] - prev_candle['close']) / prev_candle['close']) * 100
                else:
                    price_chg_pct = 0.0
                
                results.append({
                    "symbol": sym,
                    "curr_close": round(last_candle['close'], 2),
                    "prev_close": round(prev_candle['close'], 2),
                    "price_chg_pct": round(price_chg_pct, 2),
                    "curr_vol": int(last_candle['volume']),
                    "indicator_values": latest_values
                })
                
        except Exception as e:
            skipped_details.append({"symbol": sym, "reason": str(e)})

    # Sort results by price change pct
    results.sort(key=lambda r: r["price_chg_pct"], reverse=True)

    return {
        "screener": "Custom Strategy",
        "scanned": len(universe),
        "matched": len(results),
        "results": results,
        "skipped": len(skipped_details),
        "skipped_details": skipped_details,
    }
