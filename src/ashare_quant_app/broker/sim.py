from __future__ import annotations

from ashare_quant_app.broker.base import Broker
from ashare_quant_app.models import AccountSnapshot, OrderRequest, OrderResult, Position, Signal


class SimulatedBroker(Broker):
    def __init__(self, initial_cash: float = 1_000_000) -> None:
        self.cash = float(initial_cash)
        self.positions: dict[str, Position] = {}
        self.connected = False
        self._order_count = 0

    def connect(self) -> None:
        self.connected = True

    def get_account(self) -> AccountSnapshot:
        market_value = sum(position.market_value for position in self.positions.values())
        return AccountSnapshot(cash=self.cash, equity=self.cash + market_value, market_value=market_value)

    def get_positions(self) -> list[Position]:
        return list(self.positions.values())

    def place_order(self, request: OrderRequest) -> OrderResult:
        if not self.connected:
            return OrderResult(accepted=False, message="模拟券商未连接")

        self._order_count += 1
        order_id = f"SIM-{self._order_count:04d}"
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
                return OrderResult(accepted=False, message="现金不足，模拟下单失败")
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
                return OrderResult(accepted=False, message="可卖数量不足，模拟下单失败")
            existing.volume -= request.volume
            existing.available_volume -= request.volume
            existing.last_price = request.price
            self.cash += cost
            if existing.volume == 0:
                self.positions.pop(request.symbol, None)
            else:
                self.positions[request.symbol] = existing
        else:
            return OrderResult(accepted=False, message="仅支持买卖信号")

        return OrderResult(
            accepted=True,
            message=f"模拟下单成功: {request.side.value} {request.symbol} {request.volume}",
            order_id=order_id,
        )
