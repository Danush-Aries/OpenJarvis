"""Tests for the quantitative trading engine tools."""

from __future__ import annotations

import os
import json
import unittest.mock as mock
import pytest

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools.quant_trader import (
    QuantTraderTool,
    calculate_ema,
    calculate_rsi,
    calculate_std_dev,
    load_portfolio,
    save_portfolio,
)


class TestQuantTraderCalculations:
    def test_calculate_ema(self):
        prices = [10.0, 11.0, 12.0, 13.0, 14.0]
        # Length less than period -> simple average fallback
        assert calculate_ema(prices, 10) == pytest.approx(12.0)
        
        # Exact matching period
        assert calculate_ema(prices, 5) == pytest.approx(12.0)

    def test_calculate_rsi(self):
        # Flat pricing -> neutral 100 or default 50
        prices = [10.0] * 20
        assert calculate_rsi(prices, 14) == pytest.approx(50.0)
        
        # Rising pricing -> high RSI
        rising_prices = [float(x) for x in range(10, 30)]
        assert calculate_rsi(rising_prices, 14) > 50.0

    def test_calculate_std_dev(self):
        prices = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        # Standard deviation of [2, 4, 4, 4, 5, 5, 7, 9] (mean 5)
        # variance = (9 + 1 + 1 + 1 + 0 + 0 + 4 + 16) / 8 = 32 / 8 = 4.0
        # std dev = 2.0
        assert calculate_std_dev(prices, 8) == pytest.approx(2.0)


class TestQuantTraderTool:
    def test_registry(self):
        ToolRegistry.register_value("quant_trader", QuantTraderTool)
        assert ToolRegistry.contains("quant_trader")
        tool = ToolRegistry.create("quant_trader")
        assert isinstance(tool, QuantTraderTool)

    def test_spec(self):
        tool = QuantTraderTool()
        assert tool.spec.name == "quant_trader"
        assert tool.spec.category == "finance"
        assert "action" in tool.spec.parameters["properties"]
        assert "symbol" in tool.spec.parameters["properties"]
        assert "strategy" in tool.spec.parameters["properties"]

    @mock.patch("openjarvis.tools.quant_trader.load_portfolio")
    def test_execute_portfolio(self, mock_load):
        mock_load.return_value = {
            "cash_usd": 8500.0,
            "positions": {"BTC": 0.05}
        }
        tool = QuantTraderTool()
        result = tool.execute(action="portfolio")
        assert result.success is True
        assert "Capital" in result.content
        assert "Positions" in result.content or "BTC" in result.content

    def test_execute_missing_symbol(self):
        tool = QuantTraderTool()
        result = tool.execute(action="buy", amount=1)
        assert result.success is False
        assert "ticker symbol" in result.content

    @mock.patch("httpx.Client.get")
    def test_execute_ticker_sync_failure(self, mock_get):
        mock_get.side_effect = Exception("Yahoo Finance Offline")
        tool = QuantTraderTool()
        result = tool.execute(action="ticker", symbol="BTC")
        assert result.success is False
        assert "synchronization issue" in result.content

    @mock.patch("httpx.Client.get")
    @mock.patch("openjarvis.tools.quant_trader.load_portfolio")
    @mock.patch("openjarvis.tools.quant_trader.save_portfolio")
    def test_execute_buy_order_success(self, mock_save, mock_load, mock_get):
        # Mock portfolio and yahoo chart response
        mock_load.return_value = {"cash_usd": 10000.0, "positions": {}}
        
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "chart": {
                "result": [{
                    "meta": {"regularMarketPrice": 100.0},
                    "indicators": {"quote": [{"close": [95.0, 98.0, 100.0]}]}
                }]
            }
        }
        mock_get.return_value = mock_resp
        
        tool = QuantTraderTool()
        result = tool.execute(action="buy", symbol="SOL", amount=5.0)
        
        assert result.success is True
        assert "BUY SOL" in result.content
        assert "Remaining Capital" in result.content
        
        # Verify save portfolio called with correct math:
        # Cost = 100.0 * 5.0 = 500.0
        # Cash left = 10000.0 - 500.0 = 9500.0
        mock_save.assert_called_once_with({"cash_usd": 9500.0, "positions": {"SOL": 5.0}})

    @mock.patch("httpx.Client.get")
    @mock.patch("openjarvis.tools.quant_trader.load_portfolio")
    def test_execute_buy_order_insufficient_capital(self, mock_load, mock_get):
        mock_load.return_value = {"cash_usd": 100.0, "positions": {}}
        
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "chart": {
                "result": [{
                    "meta": {"regularMarketPrice": 100.0},
                    "indicators": {"quote": [{"close": [100.0]}]}
                }]
            }
        }
        mock_get.return_value = mock_resp
        
        tool = QuantTraderTool()
        result = tool.execute(action="buy", symbol="BTC", amount=2.0)
        assert result.success is False
        assert "Insufficient USD capital" in result.content

    @mock.patch("httpx.Client.get")
    @mock.patch("openjarvis.tools.quant_trader.load_portfolio")
    @mock.patch("openjarvis.tools.quant_trader.save_portfolio")
    def test_execute_sell_order_success(self, mock_save, mock_load, mock_get):
        mock_load.return_value = {"cash_usd": 5000.0, "positions": {"ETH": 4.0}}
        
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "chart": {
                "result": [{
                    "meta": {"regularMarketPrice": 1000.0},
                    "indicators": {"quote": [{"close": [1000.0]}]}
                }]
            }
        }
        mock_get.return_value = mock_resp
        
        tool = QuantTraderTool()
        result = tool.execute(action="sell", symbol="ETH", amount=2.0)
        
        assert result.success is True
        assert "SELL ETH" in result.content
        
        # Verify save portfolio called:
        # Revenue = 1000.0 * 2.0 = 2000.0
        # Cash = 5000.0 + 2000.0 = 7000.0
        # Position left = 4.0 - 2.0 = 2.0
        mock_save.assert_called_once_with({"cash_usd": 7000.0, "positions": {"ETH": 2.0}})

    @mock.patch("httpx.Client.get")
    @mock.patch("openjarvis.tools.quant_trader.load_portfolio")
    def test_execute_sell_order_insufficient_holding(self, mock_load, mock_get):
        mock_load.return_value = {"cash_usd": 1000.0, "positions": {"SOL": 1.0}}
        
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "chart": {
                "result": [{
                    "meta": {"regularMarketPrice": 100.0},
                    "indicators": {"quote": [{"close": [100.0]}]}
                }]
            }
        }
        mock_get.return_value = mock_resp
        
        tool = QuantTraderTool()
        result = tool.execute(action="sell", symbol="SOL", amount=3.0)
        assert result.success is False
        assert "Insufficient asset holding" in result.content

    @mock.patch("httpx.Client.get")
    @mock.patch("openjarvis.tools.quant_trader.load_portfolio")
    @mock.patch("openjarvis.tools.quant_trader.save_portfolio")
    def test_execute_bot_strategies(self, mock_save, mock_load, mock_get):
        # We test bot strategies with sufficient pricing candle length
        mock_load.return_value = {"cash_usd": 10000.0, "positions": {}}
        
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        # 30 daily price candles
        prices = [100.0] * 30
        mock_resp.json.return_value = {
            "chart": {
                "result": [{
                    "meta": {"regularMarketPrice": 100.0},
                    "indicators": {"quote": [{"close": prices}]}
                }]
            }
        }
        mock_get.return_value = mock_resp
        
        tool = QuantTraderTool()
        
        # 1. Test Momentum bot
        res_mom = tool.execute(action="trade_bot", symbol="BTC", strategy="momentum")
        assert res_mom.success is True
        assert "MOMENTUM" in res_mom.content
        
        # 2. Test Bollinger Mean Reversion bot
        res_rev = tool.execute(action="trade_bot", symbol="BTC", strategy="mean_reversion")
        assert res_rev.success is True
        assert "MEAN_REVERSION" in res_rev.content
        
        # 3. Test Grid Scalper bot
        res_grid = tool.execute(action="trade_bot", symbol="BTC", strategy="grid")
        assert res_grid.success is True
        assert "GRID" in res_grid.content
