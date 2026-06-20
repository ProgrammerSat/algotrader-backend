import asyncio
import os
import sys
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath("backend"))

from main import app

client = TestClient(app)

def test_api():
    # We expect a 403 or 401 if it reaches the dependency.
    # If there is a Pydantic validation error, we get a 422.
    response = client.post(
        "/api/screener/custom",
        json={
            "timeframe": "D",
            "symbols": "NSE:RELIANCE-EQ",
            "conditions": [
                {
                    "ind1": {"name": "Close", "period": None, "value": None},
                    "operator": ">",
                    "ind2": {"name": "SMA", "period": 50, "value": None}
                }
            ]
        }
    )
    print("Status Code:", response.status_code)
    print("Response JSON:", response.json())

test_api()
