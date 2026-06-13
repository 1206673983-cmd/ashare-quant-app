from __future__ import annotations

from ashare_quant_app.broker.sim import SimulatedBroker
from ashare_quant_app.models import OrderRequest, OrderStatus, Signal


def test_simulated_broker_creates_orders_trades_and_events() -> None:
    broker = SimulatedBroker(initial_cash=1_000_000)
    broker.connect()

    result = broker.place_order(
        OrderRequest(
            symbol="600519",
            side=Signal.BUY,
            price=100.0,
            volume=100,
            note="test",
        )
    )

    orders = broker.get_orders()
    trades = broker.get_trades()
    events = broker.get_events()
    positions = broker.get_positions()

    assert result.accepted is True
    assert result.status == OrderStatus.FILLED
    assert len(orders) == 1
    assert orders[0].filled_volume == 100
    assert len(trades) == 1
    assert trades[0].order_id == result.order_id
    assert len(events) >= 2
    assert positions[0].symbol == "600519"


def test_simulated_broker_rejects_cancel_for_filled_order() -> None:
    broker = SimulatedBroker(initial_cash=1_000_000)
    broker.connect()
    result = broker.place_order(
        OrderRequest(symbol="600519", side=Signal.BUY, price=100.0, volume=100)
    )

    cancel_result = broker.cancel_order(result.order_id or "")

    assert cancel_result.accepted is False
    assert cancel_result.status == OrderStatus.FILLED
