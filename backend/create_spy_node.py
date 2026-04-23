"""One-time: create SPY Company node with 2-year price_series."""
import asyncio
import json
import sys
from datetime import datetime, timedelta

import yfinance as yf

sys.path.insert(0, ".")
from app.db.neo4j_client import Neo4jClient


async def main():
    # Fetch SPY prices
    print("Fetching SPY 3-year daily prices from yfinance...")
    end = datetime.now()
    start = end - timedelta(days=1100)  # ~3 years for full coverage
    df = yf.download("SPY", start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False)
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    series = []
    for date, row in df.iterrows():
        series.append({"d": date.strftime("%Y-%m-%d"), "c": round(float(row["Close"]), 2)})

    print(f"SPY prices: {len(series)} days ({series[0]['d']} to {series[-1]['d']})")

    # Store in Neo4j
    await Neo4jClient.connect()

    await Neo4jClient.execute_query("""
        MERGE (c:Company {ticker: 'SPY'})
        SET c.name = 'SPDR S&P 500 ETF Trust',
            c.tickers = ['SPY'],
            c.price_series = $series,
            c.cik = 'SPY'
    """, {"series": json.dumps(series)})

    # Verify
    r = await Neo4jClient.execute_query(
        "MATCH (c:Company {ticker: 'SPY'}) RETURN c.price_series IS NOT NULL as has_prices"
    )
    print(f"SPY node created: has_prices={r[0]['has_prices']}")

    await Neo4jClient.disconnect()


asyncio.run(main())
