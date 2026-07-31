import os
import sqlite3
import csv
import urllib.request
import time

SYMBOLS_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "symbols.db")
URLS = [
    "https://public.fyers.in/sym_details/NSE_CM.csv",
    "https://public.fyers.in/sym_details/NSE_FO.csv",
    "https://public.fyers.in/sym_details/BSE_CM.csv",
]

def init_symbol_master():
    """Download and build the local symbol master DB if it's outdated or missing."""
    needs_update = True
    if os.path.exists(SYMBOLS_DB_PATH):
        # Check if older than 1 day (86400 seconds)
        mtime = os.path.getmtime(SYMBOLS_DB_PATH)
        if time.time() - mtime < 86400:
            needs_update = False
            
    if needs_update:
        print("🔄 Downloading Fyers Symbol Master...")
        _build_db()
        print("✅ Symbol Master updated successfully.")
    else:
        print("✅ Symbol Master is up to date.")

def _build_db():
    if os.path.exists(SYMBOLS_DB_PATH):
        os.remove(SYMBOLS_DB_PATH)
        
    conn = sqlite3.connect(SYMBOLS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE symbols (
            fyers_symbol TEXT PRIMARY KEY,
            short_name TEXT,
            description TEXT
        )
    ''')
    cursor.execute('CREATE INDEX idx_short_name ON symbols(short_name)')
    
    for url in URLS:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                content = response.read().decode('utf-8').splitlines()
                reader = csv.reader(content)
                rows_to_insert = []
                for row in reader:
                    if len(row) > 13:
                        desc = row[1]
                        fyers_symbol = row[9]
                        short_name = row[13]
                        rows_to_insert.append((fyers_symbol, short_name, desc))
                
                cursor.executemany(
                    "INSERT OR IGNORE INTO symbols (fyers_symbol, short_name, description) VALUES (?, ?, ?)",
                    rows_to_insert
                )
        except Exception as e:
            print(f"⚠️ Failed to process {url}: {e}")
            
    conn.commit()
    conn.close()

def search_symbols(query: str, limit: int = 20):
    """Search the local SQLite DB for matching symbols."""
    if not os.path.exists(SYMBOLS_DB_PATH):
        return []
        
    conn = sqlite3.connect(SYMBOLS_DB_PATH)
    cursor = conn.cursor()
    
    like_q = f"%{query.upper()}%"
    cursor.execute('''
        SELECT fyers_symbol, short_name, description 
        FROM symbols 
        WHERE short_name LIKE ? OR description LIKE ?
        ORDER BY 
            CASE WHEN short_name LIKE ? THEN 1 ELSE 2 END
        LIMIT ?
    ''', (f"{query.upper()}%", like_q, f"{query.upper()}%", limit))
    
    results = cursor.fetchall()
    conn.close()
    
    return [
        {"symbol": r[0], "short_name": r[1], "description": r[2]} 
        for r in results
    ]
