import asyncio
from datetime import datetime, timedelta
import sys
import traceback

# Adjust sys.path so we can import app
sys.path.insert(0, '/Users/saatwiksen/Desktop/Projects/SM PROJ/backend')

from app.api.screener import _fetch_chunked_history, _resample_daily_to_weekly, _resample_daily_to_monthly
from app.api.ai_screener import _sma, _rsi
from app.core.database import SessionLocal
from app.models.user import User
from app.core.fyers_client import set_fyers_client, get_fyers_client

def main():
    db = SessionLocal()
    user = db.query(User).filter(User.fyers_linked == True).first()
    if user:
        set_fyers_client(user.fyers_access_token)
    
    fyers = get_fyers_client()
    if not fyers:
        print("No fyers client")
        return
        
    symbol = "NSE:RELIANCE-EQ"
    today = datetime.today()
    start_dt = today - timedelta(days=5*365)
    
    try:
        daily_candles, err = _fetch_chunked_history(fyers, symbol, "D", start_dt, today)
        print(f"err: {err}, len(candles): {len(daily_candles) if daily_candles else 0}")
        if not err and daily_candles and len(daily_candles) > 50:
            weekly_candles = _resample_daily_to_weekly(daily_candles)
            monthly_candles = _resample_daily_to_monthly(daily_candles)
            print("Successfully resampled")
            
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
            print("Daily:", evaluate_tf(daily_candles))
            
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
            print("Asc count:", asc_count)
    except Exception as e:
        print("EXCEPTION:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
