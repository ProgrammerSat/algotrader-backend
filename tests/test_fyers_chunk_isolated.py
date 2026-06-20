import os
import sys
from datetime import datetime, timedelta
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))
from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.core.fyers_client import set_fyers_client, get_fyers_client

def test_fetch():
    db = SessionLocal()
    user = db.query(User).filter(User.fyers_linked == True).order_by(User.id.desc()).first()
    set_fyers_client(user.fyers_access_token)
    fyers = get_fyers_client()
    
    # 1. Test with current time (what screener.py does)
    today = datetime.today()
    start_dt = today - timedelta(days=50 * 7)
    end_dt = today
    
    chunk_days = 180
    cursor = start_dt
    candles1 = []
    
    while cursor <= end_dt:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end_dt)
        resp = fyers.history({
            "symbol": "NSE:RELIANCE-EQ",
            "resolution": "W",
            "date_format": 0,
            "range_from": int(cursor.timestamp()),
            "range_to": int(chunk_end.timestamp()),
            "cont_flag": "1",
        })
        if resp.get("s") == "ok":
            candles1.extend(resp.get("candles", []))
        cursor = chunk_end + timedelta(days=1)
        time.sleep(0.2)
        
    print(f"Current time logic returned {len(candles1)} candles.")

    # 2. Test with midnight time (what market.py does)
    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt = today - timedelta(days=50 * 7)
    end_dt = today
    
    cursor = start_dt
    candles2 = []
    
    while cursor <= end_dt:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end_dt)
        resp = fyers.history({
            "symbol": "NSE:RELIANCE-EQ",
            "resolution": "W",
            "date_format": 0,
            "range_from": int(cursor.timestamp()),
            "range_to": int(chunk_end.timestamp()),
            "cont_flag": "1",
        })
        if resp.get("s") == "ok":
            candles2.extend(resp.get("candles", []))
        cursor = chunk_end + timedelta(days=1)
        time.sleep(0.2)
        
    print(f"Midnight time logic returned {len(candles2)} candles.")

test_fetch()
