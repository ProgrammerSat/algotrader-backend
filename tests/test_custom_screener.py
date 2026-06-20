import asyncio
import os
import sys
import pandas as pd
import numpy as np

sys.path.append(os.path.abspath("backend"))

from app.api.screener import CustomStrategyRequest, StrategyCondition, IndicatorDef, _calculate_indicator

def test_logic():
    # Mock data
    dates = pd.date_range("2023-01-01", periods=100)
    df = pd.DataFrame({
        'timestamp': dates.astype(int) // 10**9,
        'open': np.random.randn(100) + 100,
        'high': np.random.randn(100) + 105,
        'low': np.random.randn(100) + 95,
        'close': np.random.randn(100) + 102,
        'volume': np.random.randint(1000, 10000, 100)
    })
    
    cond = StrategyCondition(
        ind1=IndicatorDef(name="Close"),
        operator=">",
        ind2=IndicatorDef(name="SMA", period=50)
    )
    
    s1 = _calculate_indicator(df, cond.ind1)
    s2 = _calculate_indicator(df, cond.ind2)
    
    val1 = s1.iloc[-1]
    val2 = s2.iloc[-1]
    
    print("val1", val1)
    print("val2", val2)
    
    match = s1.iloc[-1] > s2.iloc[-1]
    print("match", match)
    
test_logic()
