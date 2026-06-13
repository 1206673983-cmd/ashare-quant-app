from __future__ import annotations

from datetime import datetime

from ashare_quant_app.broker.base import Broker
from ashare_quant_app.models import (
    AccountSnapshot,
    BrokerEvent,
    BrokerOrder,
    EventLevel,
    OrderRequest,
    OrderResult,
    OrderStatus,
    Position,
    Signal,
    TradeFill,
)


class SimulatedBroker(Broker):
    def __init__(self, initial_cash: float = 1_000_000) -> None:
        self.cash = float(initial_cash)
        self.positions: dict[str, Position] = {}
        self.connected = False
        self._order_count = 0
        self._trade_count = 0
        self.orders: dict[str, BrokerOrder] = {}
        self.trades: list[TradeFill] = []
        self.events: list[BrokerEvent] = []

    def connect(self) -> None:
        self.connected = True
        self._record_event(EventLevel.INFO, "connection", "模拟券商连接成功")

    def get_account(self) -> AccountSnapshot:
        market_value = sum(position.market_value for position in self.positions.values())
        return AccountSnapshot(cash=self.cash, equity=self.cash + market_value, market_value=market_value)

    def get_positions(self) -> list[Position]:
        return list(self.positions.values())

    def get_orders(self) -> list[BrokerOrder]:
        return sorted(self.orders.values(), key=lambda item: item.created_at, reverse=True)

    def get_trades(self) -> list[TradeFill]:
        return sorted(self.trades, key=lambda item: item.created_at, reverse=True)

    def get_events(self) -> list[BrokerEvent]:
        return sorted(self.events, key=lambda item: item.created_at, reverse=True)

    def update_market_prices(self, prices: dict[str, float]) -> None:
        for symbol, last_price in prices.items():
            position = self.positions.get(symbol)
            if position is not None:
                position.last_price = float(last_price)

    def place_order(self, request: OrderRequest) -> OrderResult:
        if not self.connected:
            return OrderResult(accepted=False, message="模拟券商未连接", status=OrderStatus.REJECTED)

        self._order_count += 1
        order_id = f"SIM-{self._order_count:04d}"
        order = BrokerOrder(
            order_id=order_id,
            symbol=request.symbol,
            side=request.side,
            price=request.price,
            volume=request.volume,
            filled_volume=0,
            status=OrderStatus.SUBMITTED,
            message="已提交到模拟撮合引擎",
        )
        self.orders[order_id] = order
        self._record_event(
            EventLevel.INFO,
            "order",
            f"收到委托 {order_id}: {request.side.value} {request.symbol} {request.volume} @ {request.price:.2f}",
        )
        cost = request.price * request.volume
        existing = self.positions.get(
            request.symbol,
            Position(
                symbol=request.symbol,
                volume=0,
                available_volume=0,
                avg_price=0.0,
                last_price=request.price,
            ),
        )

        if request.side == Signal.BUY:
            if cost > self.cash:
                order.status = OrderStatus.REJECTED
                order.message = "现金不足，模拟下单失败"
                self._record_event(EventLevel.ERROR, "order", order.message)
                return OrderResult(
                    accepted=False,
                    message=order.message,
                    order_id=order_id,
                    status=order.status,
                )
            new_volume = existing.volume + request.volume
            weighted_cost = existing.avg_price * existing.volume + cost
            existing.volume = new_volume
            existing.available_volume = new_volume
            existing.avg_price = weighted_cost / new_volume
            existing.last_price = request.price
            self.cash -= cost
            self.positions[request.symbol] = existing
        elif request.side == Signal.SELL:
            if existing.available_volume < request.volume:
                order.status = OrderStatus.REJECTED
                order.message = "可卖数量不足，模拟下单失败"
                self._record_event(EventLevel.ERROR, "order", order.message)
                return OrderResult(
                    accepted=False,
                    message=order.message,
                    order_id=order_id,
                    status=order.status,
                )
            existing.volume -= request.volume
            existing.available_volume -= request.volume
            existing.last_price = request.price
            self.cash += cost
            if existing.volume == 0:
                self.positions.pop(request.symbol, None)
            else:
                self.positions[request.symbol] = existing
        else:
            order.status = OrderStatus.REJECTED
            order.message = "仅支持买卖信号"
            return OrderResult(accepted=False, message=order.message, order_id=order_id, status=order.status)

        self._trade_count += 1
        trade_id = f"TRD-{self._trade_count:04d}"
        trade = TradeFill(
            trade_id=trade_id,
            order_id=order_id,
            symbol=request.symbol,
            side=request.side,
            price=request.price,
            volume=request.volume,
        )
        self.trades.append(trade)
        order.status = OrderStatus.FILLED
        order.filled_volume = request.volume
        order.message = "模拟撮合已全部成交"
        order.updated_at = trade.created_at
        self._record_event(
            EventLevel.INFO,
            "trade",
            f"成交 {trade_id}: {request.side.value} {request.symbol} {request.volume} @ {request.price:.2f}",
        )

        return OrderResult(
            accepted=True,
            message=f"模拟下单成功: {request.side.value} {request.symbol} {request.volume}",
            order_id=order_id,
            status=order.status,
            trade_id=trade_id,
        )

    def cancel_order(self, order_id: str) -> OrderResult:
        order = self.orders.get(order_id)
        if order is None:
            return OrderResult(accepted=False, message="未找到指定委托", order_id=order_id, status=OrderStatus.REJECTED)
        if order.status in {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}:
            return OrderResult(
                accepted=False,
                message=f"当前委托状态为 {order.status.value}，不可撤单",
                order_id=order_id,
                status=order.status,
            )
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now()
        order.message = "模拟撤单成功"
        self._record_event(EventLevel.WARNING, "order", f"委托 {order_id} 已撤销")
        return OrderResult(accepted=True, message=order.message, order_id=order_id, status=order.status)

    def _record_event(self, level: EventLevel, category: str, message: str) -> None:
        self.events.append(BrokerEvent(level=level, category=category, message=message))
