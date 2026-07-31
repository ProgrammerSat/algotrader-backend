import yfinance as yf
ticker = yf.Ticker("RELIANCE.NS")
info = ticker.info
keys = [k for k in info.keys() if 'growth' in k.lower() or 'quarter' in k.lower() or 'rev' in k.lower()]
for k in keys:
    print(f"{k}: {info.get(k)}")
