"""Finance & investments tool — stock quotes, market data, portfolio tracking.

Gives Jarvis the ability to provide real-time market information,
stock prices, and basic portfolio tracking using free APIs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inline registry
# ---------------------------------------------------------------------------
_TOOLS: Dict[str, Any] = {}

def register(cls: Any) -> Any:
    _TOOLS[cls.__name__] = cls
    return cls

def get_tools() -> List[Any]:
    return list(_TOOLS.values())


def _get_finance_data():
    """Try to import yfinance for live stock data. Returns None if not installed."""
    try:
        import yfinance as yf
        return yf
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Stock Quote Tool
# ---------------------------------------------------------------------------


@register
class StockQuoteTool:
    """Get current and historical stock prices, market data, and company info.

    Provides real-time stock quotes, daily changes, 52-week range, market cap,
    P/E ratio, and other key financial metrics. Uses Yahoo Finance data.
    """

    tool_id = "stock_quote"
    name = "Stock Quote"
    description = """Get real-time stock price, daily change, and key financial metrics
for any publicly traded company by ticker symbol (e.g., AAPL, TSLA, MSFT, GOOGL, NVDA).
Returns current price, change %, day range, 52-week range, market cap, and P/E ratio.
Install yfinance for live data: pip install yfinance"""

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., AAPL, TSLA, MSFT, NVDA, GOOGL, AMZN)",
                },
                "period": {
                    "type": "string",
                    "enum": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "5y", "max"],
                    "description": "Historical data period",
                    "default": "1d",
                },
            },
            "required": ["ticker"],
        }

    def execute(self, ticker: str, period: str = "1d") -> Dict[str, Any]:
        ticker = ticker.upper().strip()
        yf = _get_finance_data()

        if yf is None:
            return {
                "status": "unavailable",
                "message": "yfinance is not installed. Install it with: pip install yfinance\n\n"
                           "Without yfinance, I can provide general market knowledge from my training data.",
                "ticker": ticker,
            }

        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}

            # Get current price data
            hist = stock.history(period=period)
            if hist.empty:
                return {
                    "status": "error",
                    "message": f"No data found for ticker '{ticker}'. Check the symbol and try again.",
                    "ticker": ticker,
                }

            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or hist["Close"].iloc[-1]
            previous_close = info.get("previousClose") or hist["Close"].iloc[-2] if len(hist) > 1 else current_price
            change = current_price - previous_close
            change_pct = (change / previous_close) * 100 if previous_close else 0

            result = {
                "ticker": ticker,
                "company_name": info.get("longName") or info.get("shortName") or ticker,
                "current_price": round(float(current_price), 2),
                "change": round(float(change), 2),
                "change_percent": round(float(change_pct), 2),
                "currency": info.get("currency", "USD"),
                "exchange": info.get("exchange", ""),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "volume": info.get("volume"),
                "avg_volume": info.get("averageVolume"),
                "day_high": info.get("dayHigh"),
                "day_low": info.get("dayLow"),
                "year_high": info.get("fiftyTwoWeekHigh"),
                "year_low": info.get("fiftyTwoWeekLow"),
                "dividend_yield": info.get("dividendYield"),
                "beta": info.get("beta"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
            }

            # Clean None values
            result = {k: v for k, v in result.items() if v is not None}

            return {"status": "ok", **result}

        except Exception as e:
            logger.error("Failed to get stock data for %s: %s", ticker, e)
            return {
                "status": "error",
                "message": f"Failed to retrieve data for {ticker}: {str(e)}",
                "ticker": ticker,
            }


@register
class MarketOverviewTool:
    """Get an overview of major market indices and sector performance."""

    tool_id = "market_overview"
    name = "Market Overview"
    description = "Get current state of major market indices (S&P 500, NASDAQ, Dow Jones, etc.) and their daily performance."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "include_sectors": {
                    "type": "boolean",
                    "description": "Whether to include sector performance data",
                    "default": False,
                },
            },
        }

    def execute(self, include_sectors: bool = False) -> Dict[str, Any]:
        yf = _get_finance_data()
        if yf is None:
            return {
                "status": "unavailable",
                "message": "Install yfinance for live market data: pip install yfinance",
            }

        indices = {
            "^GSPC": "S&P 500",
            "^IXIC": "NASDAQ Composite",
            "^DJI": "Dow Jones Industrial Average",
            "^RUT": "Russell 2000",
            "^VIX": "VIX Volatility Index",
            "GC=F": "Gold Futures",
            "CL=F": "Crude Oil Futures",
            "BTC-USD": "Bitcoin USD",
        }

        results = []
        for symbol, name in indices.items():
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(period="5d")
                if not hist.empty:
                    close = hist["Close"].iloc[-1]
                    prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else close
                    change = close - prev_close
                    change_pct = (change / prev_close) * 100 if prev_close else 0
                    results.append({
                        "name": name,
                        "symbol": symbol,
                        "price": round(float(close), 2),
                        "change_percent": round(float(change_pct), 2),
                    })
            except Exception:
                continue

        return {
            "status": "ok",
            "indices": results,
            "count": len(results),
            "updated": "Live",
        }


@register
class BrainstormTool:
    """Generate creative ideas, solutions, or strategies for any topic.

    Jarvis acts as an ideation companion — given a topic or problem,
    it generates diverse ideas, connects concepts, and helps think through
    possibilities from multiple angles.
    """

    tool_id = "brainstorm"
    name = "Brainstorm Ideas"
    description = """Generate creative ideas, solutions, or strategies for any topic.
Use Jarvis's knowledge and reasoning to explore possibilities,
connect concepts, and help think through problems from multiple angles.
Great for project planning, creative work, problem-solving, and strategy."""

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic, problem, or question to brainstorm about",
                },
                "angles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific angles or approaches to consider (e.g., technical, creative, practical)",
                    "default": [],
                },
                "count": {
                    "type": "integer",
                    "description": "Number of ideas to generate",
                    "default": 5,
                },
            },
            "required": ["topic"],
        }

    def execute(self, topic: str, angles: Optional[List[str]] = None, count: int = 5) -> Dict[str, Any]:
        """This tool simply signals the agent to brainstorm. The actual reasoning
        happens in the LLM's response, not in a deterministic function."""

        angle_list = angles or []
        return {
            "status": "ok",
            "topic": topic,
            "angles": angle_list,
            "count": count,
            "message": f"Brainstorming on '{topic}' from {'/'.join(angle_list) if angle_list else 'general'} perspective(s). Generating {count} ideas.",
        }
