"""Service for fetching stock price data via yfinance."""

import logging
import time
from datetime import datetime
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

    @staticmethod
    def get_price_at_date(ticker: str, target_date: str) -> Optional[dict]:
        """
        Get the close price on or nearest to target_date, plus the latest close.

        Returns dict with: price_at_date, price_current, date_used, current_date
        or None if data unavailable.
        """
        data = StockPriceService.get_price_data(ticker, "1y")
        if not data:
            return None

        try:
            target = datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            return None

        # Find closest date to target
        best = None
        best_diff = None
        for point in data:
            d = datetime.strptime(point["date"], "%Y-%m-%d")
            diff = abs((d - target).days)
            if best_diff is None or diff < best_diff:
                best = point
                best_diff = diff

        if not best:
            return None

        latest = data[-1]
        return {
            "price_at_date": best["close"],
            "date_used": best["date"],
            "price_current": latest["close"],
            "current_date": latest["date"],
        }
