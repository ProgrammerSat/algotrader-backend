import asyncio
from datetime import datetime, timedelta
import sys
import time

sys.path.insert(0, '/Users/saatwiksen/Desktop/Projects/SM PROJ/backend')

from app.core.database import SessionLocal
from app.models.user import User
from app.core.fyers_client import set_fyers_client, get_fyers_client

def main():
    db = SessionLocal()
    user = db.query(User).filter(User.fyers_linked == True).first()
    if user:
        set_fyers_client(user.fyers_access_token)
    
    fyers = get_fyers_client()
        
    symbol = "NSE:RELIANCE-EQ"
    today = datetime.today()
    start_dt = today - timedelta(days=5*365)
    
    cursor = start_dt
    end_dt = today
    
    while cursor <= end_dt:
        chunk_end = min(cursor + timedelta(days=364), end_dt)
        rf = int(cursor.timestamp())
        rt = int(chunk_end.timestamp())

        resp = fyers.history({
            "symbol":      symbol,
            "resolution":  "D",
            "date_format": 0,
            "range_from":  rf,
            "range_to":    rt,
            "cont_flag":   "1",
        })
        
        print(f"{cursor.date()} to {chunk_end.date()}: {resp.get('s')} - {resp.get('message')}")
        cursor = chunk_end + timedelta(days=1)
        time.sleep(0.1)

if __name__ == "__main__":
    main()
