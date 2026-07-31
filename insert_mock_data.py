import sys
import os
import datetime

# Add the backend directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.market_data import WMMarketSpread

def insert_mock_data():
    db = SessionLocal()
    
    mock_data = []
    
    # Generate data from July 1, 2024 to July 18, 2024
    import random
    
    base_adv = 100
    base_dec = 100
    base_bull_vol = 1500000.0
    base_bear_vol = 1000000.0
    base_trin = 1.0
    
    for day in range(1, 19):
        # Skip weekends for realism
        current_date = datetime.date(2024, 7, day)
        if current_date.weekday() >= 5:
            continue
            
        mock_data.append(
            WMMarketSpread(
                WMDate=current_date,
                WMStocksAdvToYesterday=base_adv + random.randint(-20, 50),
                WMStocksDecToYesterday=base_dec + random.randint(-30, 40),
                WMStocksAdvFrmOpenToday=base_adv + random.randint(-20, 50),
                WMStocksDecFrmOpenToday=base_dec + random.randint(-30, 40),
                WMStockBullVolYesterday=base_bull_vol + random.uniform(-200000, 300000),
                WMStockBearVolYesterday=base_bear_vol + random.uniform(-300000, 200000),
                WMStockBullVolToday=base_bull_vol + random.uniform(-200000, 400000),
                WMStockBearVolToday=base_bear_vol + random.uniform(-300000, 200000),
                WMTrinYesterday=base_trin + random.uniform(-0.2, 0.2),
                WMTrinToday=base_trin + random.uniform(-0.3, 0.3),
                WMStocksAbove200EMA=300 + random.randint(-10, 20),
                WMStocksAbove50EMA=250 + random.randint(-20, 10)
            )
        )
    
    try:
        # Check if they already exist to avoid primary key constraints, if any, or just merge
        for item in mock_data:
            db.merge(item)
        db.commit()
        print("Successfully inserted/merged mock data into wm_market_spread.")
    except Exception as e:
        db.rollback()
        print(f"Error inserting mock data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    insert_mock_data()
