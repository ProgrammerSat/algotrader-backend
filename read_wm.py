import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from app.core.database import SessionLocal
from app.models.market_data import WMIndexSentimentAnalysis

try:
    db = SessionLocal()
    results = db.query(WMIndexSentimentAnalysis).all()
    if not results:
        print("Table wm_index_sentiment_analysis is empty.")
    else:
        for row in results:
            print(f"{row.WMDate} | {row.WMIndexName} | {row.WMIndexType} | {row.WMIndexPosition} | {row.WMIndexPositiontoNifty} | {row.WMIndexWSMA30Position} | {row.WMIndexCurrentPosition}")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
