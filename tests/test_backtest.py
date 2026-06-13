from __future__ import annotations

import pandas as pd

from ashare_quant_app.engine import BacktestEngine
from ashare_quant_app.strategies import MovingAverageCrossStrategy


def test_backtest_engine_runs_with_basic_history() -> None:
    history = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=40, freq="D"),
            "close": [12 - i * 0.1 for i in range(20)] + [10 + i * 0.3 for i in range(20)],
        }
    )
    history["open"] = history["close"]
    history["high"] = history["close"] + 0.1
    history["low"] = history["close"] - 0.1
    history["volume"] = 1000

    strategy = MovingAverageCrossStrategy(fast_window=3, slow_window=5)
    engine = BacktestEngine(strategy=strategy, trade_size=100)
    result = engine.run("600519", history)

    assert result.symbol == "600519"
    assert not result.equity_curve.empty
    assert result.trades >= 1
