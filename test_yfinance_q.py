import yfinance as yf
ticker = yf.Ticker("RELIANCE.NS")
q_cash = ticker.quarterly_cash_flow

if q_cash is not None and not q_cash.empty:
    print("Rows (Metrics) in Cash Flow:")
    for row in q_cash.index:
        if 'depreciation' in row.lower():
            print("  -", row)
        print("  -", row)
else:
    print("No quarterly income statement available.")
