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

# Market cap cache: {ticker: (timestamp, market_cap)}
_market_cap_cache: dict[str, tuple[float, Optional[float]]] = {}
_MARKET_CAP_TTL = 4 * 3600  # 4 hours — market cap doesn't change fast


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

    @staticmethod
    def get_market_cap(ticker: str) -> Optional[float]:
        """Fetch market cap from yfinance. Returns value in dollars or None."""
        key = ticker.upper()
        if key in _market_cap_cache:
            ts, cap = _market_cap_cache[key]
            if time.time() - ts < _MARKET_CAP_TTL:
                return cap

        try:
            info = yf.Ticker(ticker).info
            cap = info.get("marketCap")
            if cap and cap > 0:
                _market_cap_cache[key] = (time.time(), float(cap))
                return float(cap)
            _market_cap_cache[key] = (time.time(), None)
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch market cap for {ticker}: {e}")
            _market_cap_cache[key] = (time.time(), None)
            return None

    @staticmethod
    def get_price_at_date_historical(ticker: str, target_date: str) -> Optional[dict]:
        """Fetch close price on a specific date using a tight date-range query.

        Works for any date (current or historical) — no 1y window limit.
        Returns dict with same shape as get_price_at_date, or None on failure.
        """
        try:
            import pandas as pd
            target = pd.Timestamp(target_date)
            end = (target + pd.Timedelta(days=5)).strftime("%Y-%m-%d")
            hist = yf.Ticker(ticker).history(start=target_date, end=end)
            if hist.empty:
                return None
            row = hist.iloc[0]
            date_used = hist.index[0].strftime("%Y-%m-%d")
            return {
                "price_at_date": float(row["Close"]),
                "date_used": date_used,
                "price_current": float(row["Close"]),
                "current_date": date_used,
            }
        except Exception as e:
            logger.warning(f"Failed historical price fetch for {ticker} on {target_date}: {e}")
            return None

    @staticmethod
    def get_market_cap_at_date(ticker: str, target_date: str) -> Optional[float]:
        """Historical market cap = shares_outstanding × close on target_date.

        Uses yfinance get_shares_full + history with date-range. Returns dollars or None.
        """
        try:
            import pandas as pd
            target = pd.Timestamp(target_date)
            shares_end = (target + pd.Timedelta(days=14)).strftime("%Y-%m-%d")
            hist_end = (target + pd.Timedelta(days=5)).strftime("%Y-%m-%d")
            t = yf.Ticker(ticker)
            shares = t.get_shares_full(start=target_date, end=shares_end)
            hist = t.history(start=target_date, end=hist_end)
            if shares is None or len(shares) == 0 or hist.empty:
                return None
            close = float(hist.iloc[0]["Close"])
            shares_at = float(shares.iloc[0])
            return shares_at * close
        except Exception as e:
            logger.warning(f"Failed historical mcap for {ticker} on {target_date}: {e}")
            return None
