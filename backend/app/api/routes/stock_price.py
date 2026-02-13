"""API endpoint for stock price data."""

from fastapi import APIRouter, Query

from app.services.stock_price_service import StockPriceService

router = APIRouter()


@router.get("/{ticker}")
async def get_stock_price(
    ticker: str,
    period: str = Query("1y", description="Time period: 3mo, 6mo, 1y, 2y"),
):
    """
    Get historical stock price data.

    Example:
        GET /api/stock-price/AAPL?period=1y
    """
    data = StockPriceService.get_price_data(ticker, period)
    return {
        "ticker": ticker.upper(),
        "period": period,
        "count": len(data),
        "prices": data,
    }
