from __future__ import annotations

from datetime import datetime

import pandas as pd

from ashare_quant_app.engine.backtest import BacktestResult
from ashare_quant_app.models import OrderResult, Signal, SignalDecision
from ashare_quant_app.storage import BacktestRecord, OrderRecord, Storage


def test_storage_persists_backtests_signals_and_orders(tmp_path) -> None:
    storage = Storage(tmp_path / "quant.db")

    equity_curve = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "equity": [1_000_000, 1_010_000, 1_020_000],
            "drawdown": [0.0, -0.01, -0.005],
        }
    )
    result = BacktestResult(
        symbol="600519",
        total_return=0.02,
        annual_return=0.25,
        max_drawdown=-0.01,
        sharpe=1.5,
        trades=2,
        equity_curve=equity_curve,
        trade_log=pd.DataFrame(),
    )
    storage.save_backtest(
        BacktestRecord(
            symbol="600519",
            strategy_name="moving_average_cross",
            fast_window=5,
            slow_window=20,
            trade_size=100,
            start_date="2024-01-01",
            end_date="2024-02-01",
            result=result,
        )
    )

    decision = SignalDecision(
        symbol="600519",
        signal=Signal.BUY,
        reason="快线突破慢线",
        reference_price=1680.0,
        created_at=datetime(2024, 1, 2, 10, 0, 0),
    )
    storage.save_signal(decision)
    storage.save_order(
        OrderRecord(
            symbol="600519",
            side="buy",
            price=1680.0,
            volume=100,
            reason="快线突破慢线",
            mode="DRY_RUN",
            result=OrderResult(accepted=True, message="Dry Run success", order_id="DRY-RUN"),
        )
    )

    backtests = storage.list_backtests()
    signals = storage.list_signals()
    orders = storage.list_orders()

    assert len(backtests) == 1
    assert backtests.iloc[0]["symbol"] == "600519"
    assert len(signals) == 1
    assert signals.iloc[0]["signal"] == "buy"
    assert len(orders) == 1
    assert orders.iloc[0]["order_id"] == "DRY-RUN"
