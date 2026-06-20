"""
AI Screener: Natural language → Python screener via Google Gemini.

POST /api/screener/ai
  - Sends the user's English query to Gemini
  - Gemini returns a screen() function body
  - Backend runs it safely (sandboxed exec) against Fyers OHLCV data
  - Returns matched symbols + the generated code for transparency
"""
import time
import re
import math
import json
import textwrap
from datetime import datetime, timedelta
from typing import Optional
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.fyers_client import get_fyers_client
from app.deps import get_current_user
from app.models.user import User
from app.api.screener import NIFTY50_SYMBOLS, _fetch_chunked_history, _resample_daily_to_weekly, _resample_daily_to_monthly

router = APIRouter(prefix="/api/screener", tags=["ai-screener"])

# ── TA helpers exposed to the sandboxed screen() function ──────────────────────

def _sma(prices: list, period: int) -> float:
    if len(prices) < period:
        return float("nan")
    return sum(prices[-period:]) / period


def _ema(prices: list, period: int) -> float:
    if len(prices) < period:
        return float("nan")
    k = 2 / (period + 1)
    val = sum(prices[:period]) / period
    for p in prices[period:]:
        val = p * k + val * (1 - k)
    return val


def _rsi(prices: list, period: int = 14) -> float:
    if len(prices) < period + 1:
        return float("nan")
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _stdev(prices: list, period: int) -> float:
    if len(prices) < period:
        return float("nan")
    subset = prices[-period:]
    mean = sum(subset) / period
    variance = sum((x - mean) ** 2 for x in subset) / period
    return math.sqrt(variance)


def _bb_upper(prices: list, period: int = 20, k: float = 2.0) -> float:
    m = _sma(prices, period)
    s = _stdev(prices, period)
    return m + k * s


def _bb_lower(prices: list, period: int = 20, k: float = 2.0) -> float:
    m = _sma(prices, period)
    s = _stdev(prices, period)
    return m - k * s


def _bb_width(prices: list, period: int = 20, k: float = 2.0) -> float:
    m = _sma(prices, period)
    if m == 0:
        return float("nan")
    return (_bb_upper(prices, period, k) - _bb_lower(prices, period, k)) / m * 100


def _atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return float("nan")
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    return sum(trs[-period:]) / period


def _highest(prices: list, period: int) -> float:
    if len(prices) < period:
        return float("nan")
    return max(prices[-period:])


def _lowest(prices: list, period: int) -> float:
    if len(prices) < period:
        return float("nan")
    return min(prices[-period:])


# Safe builtins and TA namespace for sandboxed exec
_SAFE_BUILTINS = {
    "abs": abs, "round": round, "min": min, "max": max,
    "sum": sum, "len": len, "range": range, "zip": zip,
    "enumerate": enumerate, "sorted": sorted, "all": all,
    "any": any, "bool": bool, "int": int, "float": float,
    "list": list, "True": True, "False": False, "None": None,
    "nan": float("nan"), "math": math,
}

_TA_NAMESPACE = {
    "sma": _sma, "ema": _ema, "rsi": _rsi,
    "stdev": _stdev, "bb_upper": _bb_upper, "bb_lower": _bb_lower,
    "bb_width": _bb_width, "atr": _atr, "highest": _highest, "lowest": _lowest,
}

# ── System prompt sent to Gemini ───────────────────────────────────────────────

_SYSTEM_PROMPT = textwrap.dedent("""
You are an expert algorithmic trading assistant that converts natural-language
stock screener queries into Python screening functions.

## Your task
Return a JSON object with exactly these keys:
{
  "title": "<short screener name>",
  "description": "<one sentence explanation of what is being screened>",
  "timeframe": "<'D' | 'W' | 'M'  — best timeframe for this query>",
  "lookback_days": <integer — how many days of history to fetch>,
  "code": "<Python function body as a string>"
}

## Function signature (DO NOT include def line — only the body)
The function receives these variables:
  closes  : list[float]   — closing prices, oldest first, most recent last
  opens   : list[float]   — opening prices
  highs   : list[float]   — high prices
  lows    : list[float]   — low prices
  volumes : list[int]     — volumes
  curr_close, prev_close  : float (last two closes)
  curr_vol, prev_vol      : float (last two volumes)
  curr_high, curr_low     : float (current candle high/low)
  curr_open               : float (current candle open)

All lists have at least 30 elements. The function MUST return True (include) or False (exclude).

## Available TA helpers (pre-computed, call directly):
  sma(prices, period)           -> float
  ema(prices, period)           -> float
  rsi(prices, period=14)        -> float (0–100)
  stdev(prices, period)         -> float
  bb_upper(prices, period, k)   -> float
  bb_lower(prices, period, k)   -> float
  bb_width(prices, period, k)   -> float   (% width relative to midband)
  atr(highs, lows, closes, n)   -> float
  highest(prices, period)       -> float
  lowest(prices, period)        -> float

## Rules
- Use ONLY the variables and helpers listed above
- NO import statements
- NO file/network/eval/exec access
- Handle edge cases: return False if any value is nan or 0 where it shouldn't be
- Keep the code clean and commented
- Return True to INCLUDE the stock, False to EXCLUDE it

## Example query: "RSI below 30 and volume surge over 50%"
Expected code body:
    r = rsi(closes, 14)
    if r != r:  # nan check
        return False
    vol_ratio = curr_vol / prev_vol if prev_vol > 0 else 0
    return r < 30 and vol_ratio > 1.5

Now respond with ONLY valid JSON (no markdown, no explanation).
""").strip()


# ── Gemini call ────────────────────────────────────────────────────────────────

class GeminiScreenerResponse(BaseModel):
    title: str
    description: str
    timeframe: str
    lookback_days: int
    code: str


@lru_cache(maxsize=128)
def _call_gemini(query: str, api_key: str) -> dict:
    """Call Gemini API and return parsed JSON response (uses google-genai SDK)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=query,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.2,
            max_output_tokens=2048,
            response_mime_type="application/json",
            response_schema=GeminiScreenerResponse,
        ),
    )

    raw = response.text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw: {raw[:500]}")


# ── Sandboxed execution ────────────────────────────────────────────────────────

def _build_screen_fn(code_body: str):
    """
    Compile user-supplied code body into a callable screen() function.
    Runs in a restricted namespace — no builtins beyond the safe list.
    """
    fn_src = "def _screen(closes,opens,highs,lows,volumes," \
             "curr_close,prev_close,curr_vol,prev_vol,curr_high,curr_low,curr_open):\n"
    for line in code_body.strip().splitlines():
        fn_src += f"    {line}\n"

    ns = {"__builtins__": _SAFE_BUILTINS, **_TA_NAMESPACE}
    exec(compile(fn_src, "<ai_screen>", "exec"), ns)  # noqa: S102
    return ns["_screen"]


# ── Fyers data fetch ───────────────────────────────────────────────────────────

def _fetch_candles(fyers, symbol: str, resolution: str, rf: int, rt: int):
    # Pass datetime objects instead of timestamps to _fetch_chunked_history
    start_dt = datetime.fromtimestamp(rf)
    end_dt = datetime.fromtimestamp(rt)
    
    if resolution == "W":
        daily_candles, err = _fetch_chunked_history(fyers, symbol, "D", start_dt, end_dt)
        if err:
            return None, err
        candles = _resample_daily_to_weekly(daily_candles)
    elif resolution == "M":
        daily_candles, err = _fetch_chunked_history(fyers, symbol, "D", start_dt, end_dt)
        if err:
            return None, err
        candles = _resample_daily_to_monthly(daily_candles)
    else:
        # D
        candles, err = _fetch_chunked_history(fyers, symbol, resolution, start_dt, end_dt)
        if err:
            return None, err
            
    if not candles:
        return None, "No data returned"
    if len(candles) < 30:
        return None, f"Insufficient history ({len(candles)} candles, need 30)"
        
    return candles, None


# ── Request / Response models ──────────────────────────────────────────────────

class AIScreenerRequest(BaseModel):
    query: str
    symbols: Optional[str] = None  # comma-separated; blank = Nifty 50


class AIScreenerResponse(BaseModel):
    screener:     str
    description:  str
    timeframe:    str
    generated_code: str
    scanned:      int
    matched:      int
    skipped:      int
    skipped_details: list
    results:      list


# ── Main endpoint ──────────────────────────────────────────────────────────────

@router.post("/ai", response_model=AIScreenerResponse)
def ai_screener(
    req: AIScreenerRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Natural language → live screener powered by Google Gemini.

    1. Sends the user query to Gemini which returns a Python screen() body.
    2. Fetches OHLCV candles for each symbol from Fyers.
    3. Runs the generated function in a sandboxed exec() per symbol.
    4. Returns matches + generated code for full transparency.
    """
    settings = get_settings()

    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "Gemini API key not configured. "
                "Add GEMINI_API_KEY to backend/.env and restart the server. "
                "Get a free key at https://aistudio.google.com/apikey"
            ),
        )

    fyers = get_fyers_client()
    if not fyers:
        raise HTTPException(status_code=403, detail="Fyers account not linked.")

    # 1. Call Gemini
    try:
        gemini_out = _call_gemini(req.query, settings.gemini_api_key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gemini error: {e}")

    title        = gemini_out.get("title", "AI Screener")
    description  = gemini_out.get("description", req.query)
    timeframe    = gemini_out.get("timeframe", "W")
    lookback     = int(gemini_out.get("lookback_days", 180))
    code_body    = gemini_out.get("code", "")

    if not code_body:
        raise HTTPException(status_code=502, detail="Gemini returned empty code.")

    # 2. Build screen function
    try:
        screen_fn = _build_screen_fn(code_body)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Code compile error: {e}")

    # 3. Determine universe
    universe = (
        [s.strip() for s in req.symbols.split(",") if s.strip()]
        if req.symbols else NIFTY50_SYMBOLS
    )

    # Guarantee enough calendar days for 30 candles
    if timeframe == "W":
        lookback = max(lookback, 30 * 7 + 30)
    elif timeframe == "M":
        lookback = max(lookback, 30 * 30 + 30)
    else:
        lookback = max(lookback, 30 + 15)

    today = datetime.today()
    rf = int((today - timedelta(days=lookback)).timestamp())
    rt = int(today.timestamp())

    results        = []
    skipped_details = []

    print(f"🤖 AI Screener: '{title}' | {len(universe)} symbols | TF={timeframe}")

    # 4. Screen each symbol
    for sym in universe:
        try:
            candles, err = _fetch_candles(fyers, sym, timeframe, rf, rt)
            time.sleep(0.08)

            if err:
                skipped_details.append({"symbol": sym, "reason": err})
                continue

            opens   = [c[1] for c in candles]
            highs   = [c[2] for c in candles]
            lows    = [c[3] for c in candles]
            closes  = [c[4] for c in candles]
            volumes = [c[5] for c in candles]

            curr_close = closes[-1];  prev_close = closes[-2]
            curr_vol   = volumes[-1]; prev_vol   = volumes[-2]
            curr_high  = highs[-1];   curr_low   = lows[-1]
            curr_open  = opens[-1]

            matched = screen_fn(
                closes, opens, highs, lows, volumes,
                curr_close, prev_close, curr_vol, prev_vol,
                curr_high, curr_low, curr_open,
            )

            if matched:
                pct_chg = ((curr_close - prev_close) / prev_close * 100) if prev_close else 0
                vol_ratio = (curr_vol / prev_vol) if prev_vol else 0
                results.append({
                    "symbol":        sym,
                    "curr_close":    round(curr_close, 2),
                    "prev_close":    round(prev_close, 2),
                    "price_chg_pct": round(pct_chg, 2),
                    "curr_vol":      curr_vol,
                    "prev_vol":      prev_vol,
                    "vol_ratio":     round(vol_ratio, 4),
                    "curr_high":     round(curr_high, 2),
                    "curr_low":      round(curr_low, 2),
                    "curr_open":     round(curr_open, 2),
                    # Expose extra computed values for display
                    "rsi_14":        round(_rsi(closes, 14), 2),
                    "sma_20":        round(_sma(closes, 20), 2),
                })

        except Exception as e:
            skipped_details.append({"symbol": sym, "reason": str(e)})

    results.sort(key=lambda r: r["price_chg_pct"], reverse=True)
    print(f"✅ AI Scan done. Matched: {len(results)}, Skipped: {len(skipped_details)}")

    return AIScreenerResponse(
        screener=title,
        description=description,
        timeframe=timeframe,
        generated_code=code_body,
        scanned=len(universe),
        matched=len(results),
        skipped=len(skipped_details),
        skipped_details=skipped_details,
        results=results,
    )
