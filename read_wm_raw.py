import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from app.core.database import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM wm_index_sentiment_analysis LIMIT 20"))
        rows = result.fetchall()
        if not rows:
            print("Table is empty")
        else:
            for row in rows:
                print(dict(row._mapping))
except Exception as e:
    print(f"Error: {e}")
