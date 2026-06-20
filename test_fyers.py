import asyncio
from datetime import datetime, timedelta
import sys

# Adjust sys.path so we can import app
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
    if not fyers:
        print("No fyers client")
        return
        
    symbol = "NSE:RELIANCE-EQ"
    today = datetime.today()
    start_dt = today - timedelta(days=365)
    
    rf = int(start_dt.timestamp())
    rt = int(today.timestamp())

    resp = fyers.history({
        "symbol":      symbol,
        "resolution":  "D",
        "date_format": 0,
        "range_from":  rf,
        "range_to":    rt,
        "cont_flag":   "1",
    })
    
    print("Raw Fyers Response:", resp)

if __name__ == "__main__":
    main()
