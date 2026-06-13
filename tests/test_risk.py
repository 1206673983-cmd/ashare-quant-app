from __future__ import annotations

from ashare_quant_app.config import RiskConfig
from ashare_quant_app.engine.risk import RiskManager
from ashare_quant_app.models import Position, Signal


def test_risk_manager_triggers_stop_loss_exit() -> None:
    manager = RiskManager(RiskConfig(stop_loss_pct=0.05, take_profit_pct=0.2))
    position = Position(symbol="600519", volume=100, available_volume=100, avg_price=100.0, last_price=100.0)

    decision = manager.maybe_force_exit("600519", position, last_price=94.0)

    assert decision is not None
    assert decision.signal == Signal.SELL
    assert "止损" in decision.reason


def test_risk_manager_blocks_frequent_buys_but_not_sells() -> None:
    manager = RiskManager(RiskConfig(max_daily_trades=5, min_trade_interval_seconds=3600))
    manager.record_trade("600519")

    buy_message = manager.validate_order("600519", Signal.BUY)
    sell_message = manager.validate_order("600519", Signal.SELL)

    assert buy_message is not None
    assert "最小间隔" in buy_message
    assert sell_message is None
