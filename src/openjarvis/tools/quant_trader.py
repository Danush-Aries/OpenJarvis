"""Quant Investment & Trading Manager — Public ticker retrieval and paper trading engine."""

from __future__ import annotations

import os
import json
import httpx
from typing import Any, Dict, List
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

PORTFOLIO_FILE = "/Users/dhanush/Desktop/Jarvis/dashboard/portfolio.json"

def load_portfolio() -> Dict[str, Any]:
    if not os.path.exists(PORTFOLIO_FILE):
        default_portfolio = {
            "cash_usd": 10000.0,
            "positions": {}
        }
        save_portfolio(default_portfolio)
        return default_portfolio
    try:
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"cash_usd": 10000.0, "positions": {}}

def save_portfolio(portfolio: Dict[str, Any]):
    try:
        with open(PORTFOLIO_FILE, "w") as f:
            json.dump(portfolio, f, indent=4)
    except Exception as e:
        print(f"Error saving portfolio: {e}")

def calculate_ema(prices: List[float], period: int) -> float:
    if len(prices) < period:
        return sum(prices) / len(prices) if prices else 0.0
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price * k) + (ema * (1 - k))
    return ema

def calculate_rsi(prices: List[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))
            
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
        
    for idx in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[idx]) / period
        avg_loss = (avg_loss * (period - 1) + losses[idx]) / period
        
    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_std_dev(prices: List[float], period: int = 20) -> float:
    if len(prices) < period:
        return 0.0
    slice_prices = prices[-period:]
    mean = sum(slice_prices) / period
    variance = sum((p - mean) ** 2 for p in slice_prices) / period
    return variance ** 0.5



@ToolRegistry.register("quant_trader")
class QuantTraderTool(BaseTool):
    """Executes paper trades, checks live tickers, and runs automated momentum bot strategies without keys."""

    tool_id = "quant_trader"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="quant_trader",
            description=(
                "Query live crypto/stock market tickers (using keyless public feeds), "
                "perform quantitative momentum analysis (RSI/EMA/MACD), place paper trades, "
                "and run the automated trading bot strategy loop natively."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action: 'ticker', 'buy', 'sell', 'portfolio', or 'trade_bot' (runs quantitative strategy loop).",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Ticker symbol (e.g. 'BTC' for Bitcoin, 'AAPL' for Apple, 'SOL' for Solana).",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Asset amount to purchase or sell.",
                    },
                    "strategy": {
                        "type": "string",
                        "description": "Bot strategy: 'momentum', 'mean_reversion', or 'grid'. Default is 'momentum'.",
                    },
                },
                "required": ["action"],
            },
            category="finance",
        )

    def execute(self, **params: Any) -> ToolResult:
        action = params.get("action", "").lower().strip()
        symbol = params.get("symbol", "").upper().strip()
        strategy = params.get("strategy", "momentum").lower().strip()

        # Check Portfolio
        if action == "portfolio":
            portfolio = load_portfolio()
            pos_lines = []
            for asset, qty in portfolio.get("positions", {}).items():
                if qty > 0:
                    pos_lines.append(f"- **{asset}**: {qty:.6f} units")
            
            content = (
                f"### J.A.R.V.I.S. QUANTITATIVE INVESTMENT MATRIX\n\n"
                f"*   **Available Capital**: ${portfolio.get('cash_usd', 10000.0):,.2f} USD\n"
                f"*   **Active Holdings**:\n"
            )
            if pos_lines:
                content += "\n".join(pos_lines)
            else:
                content += "No active positions. Cash reserves fully liquid."
                
            return ToolResult(
                tool_name="quant_trader",
                content=content,
                success=True,
                metadata=portfolio,
            )

        if not symbol:
            return ToolResult(
                tool_name="quant_trader",
                content="Please provide a ticker symbol (e.g. 'BTC', 'AAPL').",
                success=False,
            )

        # Get Live Historical price candles for Ticker & Bot Actions
        prices_close = []
        current_price = 0.0
        
        try:
            # We pull the last 1 month of daily closing candles natively from Yahoo Finance keyless chart API
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1mo&interval=1d"
            headers = {"User-Agent": "Mozilla/5.0"}
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    result = resp.json()["chart"]["result"][0]
                    meta = result["meta"]
                    current_price = float(meta["regularMarketPrice"])
                    
                    # Extract list of closing prices
                    closes = result["indicators"]["quote"][0]["close"]
                    prices_close = [float(p) for p in closes if p is not None]
                    
            if current_price <= 0.0:
                raise ValueError("Retrieved regular market price is zero or negative.")

        except Exception as e:
            return ToolResult(
                tool_name="quant_trader",
                content=f"I apologize, sir. I encountered a live data synchronization issue: {str(e)}. I cannot execute this telemetry request to guarantee 100% data accuracy.",
                success=False,
            )

        # Action 2: Get Price Ticker & Analysis
        if action == "ticker":
            ema_20 = calculate_ema(prices_close, 20) or (current_price * 0.98)
            rsi = calculate_rsi(prices_close, 14)
            trend = "BULLISH MOMENTUM" if rsi > 50 else "BEARISH COMPRESSION"
            
            content = (
                f"### Active Ticker Diagnostic: {symbol}\n"
                f"*   **Live Price**: ${current_price:,.2f} USD\n"
                f"*   **20-day Exponential Moving Average (EMA-20)**: ${ema_20:,.2f}\n"
                f"*   **Relative Strength Index (RSI-14)**: {rsi:.1f} ({'Overbought' if rsi > 70 else 'Oversold' if rsi < 30 else 'Neutral'})\n"
                f"*   **Trend Compilation**: {trend}\n\n"
                f"Recommendation: System indicates a dynamic hold pattern, sir."
            )
            return ToolResult(
                tool_name="quant_trader",
                content=content,
                success=True,
                metadata={"symbol": symbol, "price": current_price, "rsi": rsi, "ema_20": ema_20},
            )

        # Action 3: God-Tier Algorithmic Quantitative Bot Strategy
        elif action == "trade_bot":
            if len(prices_close) < 15:
                return ToolResult(
                    tool_name="quant_trader",
                    content="Insufficient historical data length to execute technical strategies, sir.",
                    success=False,
                )
            
            # Calculate Universal Indicators
            ema_12 = calculate_ema(prices_close, 12)
            ema_26 = calculate_ema(prices_close, 26)
            ema_20 = calculate_ema(prices_close, 20)
            rsi = calculate_rsi(prices_close, 14)
            macd_val = ema_12 - ema_26
            
            # Bollinger Bands for Mean Reversion
            std_dev = calculate_std_dev(prices_close, 20)
            upper_band = ema_20 + (2.0 * std_dev) if std_dev > 0 else (current_price * 1.05)
            lower_band = ema_20 - (2.0 * std_dev) if std_dev > 0 else (current_price * 0.95)
            
            signal = "HOLD"
            decision_desc = ""
            
            # Apply Selected Strategy Logic
            if strategy == "mean_reversion":
                if current_price <= lower_band:
                    signal = "BUY"
                    decision_desc = f"Price (${current_price:,.2f}) has fallen below the Lower Bollinger Band (${lower_band:,.2f}). Mean reversion indicates strong OVERSOLD territory."
                elif current_price >= upper_band:
                    signal = "SELL"
                    decision_desc = f"Price (${current_price:,.2f}) has breached the Upper Bollinger Band (${upper_band:,.2f}). Mean reversion indicates strong OVERBOUGHT territory."
                else:
                    signal = "HOLD"
                    decision_desc = f"Price (${current_price:,.2f}) is circulating inside the Bollinger envelope (${lower_band:,.2f} - ${upper_band:,.2f}). No mean reversion active."
            
            elif strategy == "grid":
                deviation_pct = ((current_price - ema_20) / ema_20) * 100.0 if ema_20 > 0 else 0.0
                if deviation_pct <= -2.0:
                    signal = "BUY"
                    decision_desc = f"Price (${current_price:,.2f}) is deviation-compressed {deviation_pct:.2f}% below the EMA-20 average (${ema_20:,.2f}). Grid Scalper BUY threshold breached."
                elif deviation_pct >= 2.0:
                    signal = "SELL"
                    decision_desc = f"Price (${current_price:,.2f}) is deviation-inflated +{deviation_pct:.2f}% above the EMA-20 average (${ema_20:,.2f}). Grid Scalper LIQUIDATION threshold breached."
                else:
                    signal = "HOLD"
                    decision_desc = f"Price is matching EMA-20 within a tight range ({deviation_pct:.2f}% deviation). Grid Scalper holds position."
                    
            else: # default to momentum
                strategy = "momentum"
                if rsi < 30:
                    signal = "BUY"
                    decision_desc = f"RSI level ({rsi:.1f}) indicates extremely OVERSOLD momentum. Primary buy signal active!"
                elif rsi > 70:
                    signal = "SELL"
                    decision_desc = f"RSI level ({rsi:.1f}) indicates extremely OVERBOUGHT momentum. Target liquidation signal active!"
                elif macd_val > 0 and ema_12 > ema_26:
                    signal = "BULLISH BUY"
                    decision_desc = f"Bullish EMA crossover detected (EMA-12: ${ema_12:,.2f} > EMA-26: ${ema_26:,.2f}). Upward trend active."
                elif macd_val < 0 and ema_12 < ema_26:
                    signal = "BEARISH LIQUIDATE"
                    decision_desc = f"Bearish EMA crossover detected (EMA-12: ${ema_12:,.2f} < EMA-26: ${ema_26:,.2f}). Downward compression active."
                else:
                    signal = "HOLD"
                    decision_desc = "RSI is neutral and indicators suggest consolidation."
            
            # Automatically transact dry-run trade if signal matches
            portfolio = load_portfolio()
            auto_trade_logs = []
            
            if signal in ["BUY", "BULLISH BUY"]:
                # Check available cash to paper buy
                cash = portfolio.get("cash_usd", 10000.0)
                amount_to_buy = 1000.0 / current_price # Default $1000 order size
                cost = current_price * amount_to_buy
                
                if cash >= cost:
                    portfolio["cash_usd"] = cash - cost
                    portfolio["positions"][symbol] = portfolio["positions"].get(symbol, 0.0) + amount_to_buy
                    save_portfolio(portfolio)
                    auto_trade_logs.append(f"[BOT ORDER] Automatically executed paper BUY of {amount_to_buy:.4f} {symbol} at ${current_price:,.2f} ($1,000 allocation).")
                else:
                    auto_trade_logs.append("[BOT ORDER] Buy signal triggered, but USD reserves are fully locked.")
            
            elif signal in ["SELL", "BEARISH LIQUIDATE"]:
                # Liquidate position
                qty = portfolio.get("positions", {}).get(symbol, 0.0)
                if qty > 0:
                    revenue = current_price * qty
                    portfolio["cash_usd"] = portfolio.get("cash_usd", 10000.0) + revenue
                    del portfolio["positions"][symbol]
                    save_portfolio(portfolio)
                    auto_trade_logs.append(f"[BOT ORDER] Automatically executed paper LIQUIDATION of {qty:.4f} {symbol} at ${current_price:,.2f} (Total Revenue: ${revenue:,.2f} USD).")
            
            trade_notes = "\n".join(auto_trade_logs) if auto_trade_logs else "No automated transaction transacted. Holding current position."
            
            content = (
                f"### J.A.R.V.I.S. QUANTITATIVE ALGORITHMIC BOT MATRIX: {symbol}\n"
                f"*   **Strategy Profile**: {strategy.upper()}\n"
                f"*   **Current Price**: ${current_price:,.2f} USD\n"
                f"*   **Exponential Moving Average 12 (EMA-12)**: ${ema_12:,.2f}\n"
                f"*   **Exponential Moving Average 26 (EMA-26)**: ${ema_26:,.2f}\n"
                f"*   **EMA-20 Midline**: ${ema_20:,.2f}\n"
                f"*   **Bollinger Upper Band (2.0s)**: ${upper_band:,.2f}\n"
                f"*   **Bollinger Lower Band (2.0s)**: ${lower_band:,.2f}\n"
                f"*   **MACD Divergence Metric**: {macd_val:,.4f}\n"
                f"*   **Relative Strength Index (RSI-14)**: {rsi:.1f}\n"
                f"*   **Bot Recommendation**: **{signal}**\n\n"
                f"**Diagnostics & Action Matrix**:\n"
                f"> {decision_desc}\n\n"
                f"**Execution Logs**:\n"
                f"{trade_notes}"
            )
            
            return ToolResult(
                tool_name="quant_trader",
                content=content,
                success=True,
                metadata={
                    "symbol": symbol,
                    "price": current_price,
                    "rsi": rsi,
                    "macd": macd_val,
                    "ema_12": ema_12,
                    "ema_26": ema_26,
                    "ema_20": ema_20,
                    "upper_band": upper_band,
                    "lower_band": lower_band,
                    "signal": signal,
                    "strategy": strategy
                },
            )

        # Paper Buy Tactic
        elif action == "buy":
            amount = float(params.get("amount", 0.0))
            if amount <= 0.0:
                return ToolResult(
                    tool_name="quant_trader",
                    content="Please provide a positive amount to purchase.",
                    success=False,
                )
            
            cost = current_price * amount
            portfolio = load_portfolio()
            cash = portfolio.get("cash_usd", 10000.0)
            
            if cost > cash:
                return ToolResult(
                    tool_name="quant_trader",
                    content=f"Insufficient USD capital, sir. Required: ${cost:,.2f}, Available: ${cash:,.2f}.",
                    success=False,
                )
                
            portfolio["cash_usd"] = cash - cost
            portfolio["positions"][symbol] = portfolio["positions"].get(symbol, 0.0) + amount
            save_portfolio(portfolio)
            
            return ToolResult(
                tool_name="quant_trader",
                content=(
                    f"### Paper Order Transacted: BUY {symbol}\n"
                    f"*   **Quantity**: {amount:.6f} units\n"
                    f"*   **Execution Price**: ${current_price:,.2f} USD / unit\n"
                    f"*   **Total Cost**: ${cost:,.2f} USD\n"
                    f"*   **Remaining Capital**: ${portfolio['cash_usd']:,.2f} USD\n\n"
                    f"Diagnostics: Trade successfully logged into `portfolio.json` matrix, Dhanush."
                ),
                success=True,
                metadata=portfolio
            )

        # Paper Sell Tactic
        elif action == "sell":
            amount = float(params.get("amount", 0.0))
            if amount <= 0.0:
                return ToolResult(
                    tool_name="quant_trader",
                    content="Please provide a positive amount to sell.",
                    success=False,
                )
                
            portfolio = load_portfolio()
            qty = portfolio.get("positions", {}).get(symbol, 0.0)
            
            if qty < amount:
                return ToolResult(
                    tool_name="quant_trader",
                    content=f"Insufficient asset holding. Required: {amount:.6f} {symbol}, Owned: {qty:.6f} {symbol}.",
                    success=False,
                )
                
            revenue = current_price * amount
            portfolio["cash_usd"] = portfolio.get("cash_usd", 10000.0) + revenue
            portfolio["positions"][symbol] = qty - amount
            
            if portfolio["positions"][symbol] <= 0:
                del portfolio["positions"][symbol]
                
            save_portfolio(portfolio)
            
            return ToolResult(
                tool_name="quant_trader",
                content=(
                    f"### Paper Order Transacted: SELL {symbol}\n"
                    f"*   **Quantity**: {amount:.6f} units\n"
                    f"*   **Execution Price**: ${current_price:,.2f} USD / unit\n"
                    f"*   **Total Revenue**: ${revenue:,.2f} USD\n"
                    f"*   **Remaining Capital**: ${portfolio['cash_usd']:,.2f} USD\n\n"
                    f"Diagnostics: Asset successfully liquidated and balance credited, sir."
                ),
                success=True,
                metadata=portfolio
            )

        return ToolResult(
            tool_name="quant_trader",
            content=f"Unknown financial matrix action: '{action}'",
            success=False,
        )


__all__ = ["QuantTraderTool"]
