import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from app.core.database import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT DISTINCT WMIndexName FROM wm_index_sentiment_analysis"))
        rows = result.fetchall()
        for row in rows:
            print(row[0])
except Exception as e:
    print(f"Error: {e}")
