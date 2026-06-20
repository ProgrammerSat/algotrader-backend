import asyncio
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))
from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.core.fyers_client import set_fyers_client, get_fyers_client
from backend.app.api.screener import _fetch_chunked_history

db = SessionLocal()
user = db.query(User).filter(User.fyers_linked == True).order_by(User.id.desc()).first()
set_fyers_client(user.fyers_access_token)
fyers = get_fyers_client()

today = datetime.today()
start_dt = today - timedelta(days=50 * 7)
end_dt = today

candles, err = _fetch_chunked_history(fyers, "NSE:RELIANCE-EQ", "W", start_dt, end_dt)
print(f"Candles count: {len(candles) if candles else 0}")
if err:
    print(f"Error: {err}")
if candles:
    print(f"First candle: {datetime.fromtimestamp(candles[0][0])}")
    print(f"Last candle: {datetime.fromtimestamp(candles[-1][0])}")
