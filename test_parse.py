import urllib.parse
db_url = "sqlite+libsql://algotrader-programmersat.aws-ap-south-1.turso.io/?authToken=eyJhbGci&secure=true"

parsed = urllib.parse.urlparse(db_url)
query = urllib.parse.parse_qs(parsed.query)

token = None
if "authToken" in query:
    token = query["authToken"][0]
    del query["authToken"]

# reconstruct
new_query = urllib.parse.urlencode(query, doseq=True)
new_parsed = parsed._replace(query=new_query)
new_url = urllib.parse.urlunparse(new_parsed)

print(f"Token: {token}")
print(f"URL: {new_url}")
