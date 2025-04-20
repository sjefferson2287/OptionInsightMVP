import os
from alpha_vantage.timeseries import TimeSeries
from polygon import RESTClient

# Alpha Vantage test
av_key = os.getenv("ALPHA_VANTAGE_KEY")
print("AV Key:", av_key)
if av_key:
    ts = TimeSeries(key=av_key, output_format="pandas")
    df, _ = ts.get_daily("AAPL", outputsize="compact")
# AlphaVantage columns: "1. open", "2. high", "3. low", "4. close", "5. volume"
df = df.rename(columns={
    "1. open": "Open",
    "2. high": "High",
    "3. low": "Low",
    "4. close": "Close",
    "5. volume": "Volume"
})
print("AAPL Close (last 3):\n", df["Close"].tail(3))


# Polygon test
client = RESTClient(api_key=os.getenv("POLYGON_API_KEY"))

# Fetch a full chain snapshot for AAPL expiring 2025‑04‑25
options_iter = client.list_snapshot_options_chain(
    "AAPL",
    params={"expiration_date": "2025-04-25"}
)

# Convert to list so we can get a length and slice it
options = list(options_iter)

print(f"Fetched {len(options)} contracts. Sample:")
for opt in options[:3]:
    print(opt.contract_symbol, f"Δ={opt.greeks.delta:.2f}", f"IV={opt.greeks.implied_volatility:.1%}")
