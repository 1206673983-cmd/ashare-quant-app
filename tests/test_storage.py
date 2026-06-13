from __future__ import annotations

from datetime import datetime

import pandas as pd

from ashare_quant_app.engine.backtest import BacktestResult
from ashare_quant_app.models import AccountSnapshot, BrokerEvent, BrokerOrder, EventLevel, OrderResult, OrderStatus, Position, Signal, SignalDecision, TradeFill
from ashare_quant_app.storage import AccountSnapshotRecord, BacktestRecord, OrderRecord, Storage


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
            result=OrderResult(
                accepted=True,
                message="Dry Run success",
                order_id="DRY-RUN",
                status=OrderStatus.FILLED,
                trade_id="TRD-0001",
            ),
        )
    )
    storage.save_broker_orders(
        [
            BrokerOrder(
                order_id="SIM-0001",
                symbol="600519",
                side=Signal.BUY,
                price=1680.0,
                volume=100,
                filled_volume=100,
                status=OrderStatus.FILLED,
                message="已成交",
            )
        ]
    )
    storage.save_trades(
        [
            TradeFill(
                trade_id="TRD-0001",
                order_id="SIM-0001",
                symbol="600519",
                side=Signal.BUY,
                price=1680.0,
                volume=100,
            )
        ]
    )
    storage.save_account_snapshot(
        AccountSnapshotRecord(
            account=AccountSnapshot(cash=800000, equity=1_000_000, market_value=200000),
            source="test",
        )
    )
    storage.save_position_snapshot(
        [
            Position(
                symbol="600519",
                volume=100,
                available_volume=100,
                avg_price=1680.0,
                last_price=1700.0,
            )
        ],
        source="test",
    )
    storage.save_events(
        [
            BrokerEvent(
                level=EventLevel.INFO,
                category="order",
                message="模拟委托已成交",
            )
        ]
    )

    backtests = storage.list_backtests()
    signals = storage.list_signals()
    orders = storage.list_orders()
    broker_orders = storage.list_broker_orders()
    trades = storage.list_trades()
    accounts = storage.list_account_snapshots()
    positions = storage.list_position_snapshots()
    events = storage.list_events()

    assert len(backtests) == 1
    assert backtests.iloc[0]["symbol"] == "600519"
    assert len(signals) == 1
    assert signals.iloc[0]["signal"] == "buy"
    assert len(orders) == 1
    assert orders.iloc[0]["order_id"] == "DRY-RUN"
    assert orders.iloc[0]["trade_id"] == "TRD-0001"
    assert len(broker_orders) == 1
    assert broker_orders.iloc[0]["status"] == "filled"
    assert len(trades) == 1
    assert trades.iloc[0]["trade_id"] == "TRD-0001"
    assert len(accounts) == 1
    assert accounts.iloc[0]["source"] == "test"
    assert len(positions) == 1
    assert positions.iloc[0]["symbol"] == "600519"
    assert len(events) == 1
    assert events.iloc[0]["category"] == "order"
