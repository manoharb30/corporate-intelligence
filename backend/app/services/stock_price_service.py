"""Service for fetching stock price data via yfinance."""

import logging
import time
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)

# Simple in-memory cache: {ticker_period: (timestamp, data)}
_cache: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 3600  # 1 hour


class StockPriceService:
    """Fetches and caches stock price data."""

    VALID_PERIODS = {"3mo", "6mo", "1y", "2y"}

    @staticmethod
    def get_price_data(ticker: str, period: str = "1y") -> list[dict]:
        """
        Get historical price data for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            period: Time period - 3mo, 6mo, 1y, 2y

        Returns:
            List of {date, open, high, low, close, volume} dicts
        """
        if period not in StockPriceService.VALID_PERIODS:
            period = "1y"

        cache_key = f"{ticker.upper()}_{period}"

        # Check cache
        if cache_key in _cache:
            ts, data = _cache[cache_key]
            if time.time() - ts < _CACHE_TTL:
                return data

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)

            if df.empty:
                return []

            data = []
            for date, row in df.iterrows():
                data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "open": round(row["Open"], 2),
                    "high": round(row["High"], 2),
                    "low": round(row["Low"], 2),
                    "close": round(row["Close"], 2),
                    "volume": int(row["Volume"]),
                })

            # Cache result
            _cache[cache_key] = (time.time(), data)
            return data

        except Exception as e:
            logger.error(f"Failed to fetch price data for {ticker}: {e}")
            return []
