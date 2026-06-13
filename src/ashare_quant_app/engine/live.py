from __future__ import annotations

from ashare_quant_app.broker.base import Broker
from ashare_quant_app.config import AppConfig
from ashare_quant_app.data import DataProvider
from ashare_quant_app.models import OrderRequest, OrderResult, Signal, SignalDecision
from ashare_quant_app.strategies.base import Strategy


class LiveTradingEngine:
    def __init__(
        self,
        strategy: Strategy,
        data_provider: DataProvider,
        broker: Broker,
        config: AppConfig,
    ) -> None:
        self.strategy = strategy
        self.data_provider = data_provider
        self.broker = broker
        self.config = config

    def evaluate_symbol(self, symbol: str) -> SignalDecision:
        positions = {position.symbol: position for position in self.broker.get_positions()}
        position = positions.get(symbol)
        position_size = position.available_volume if position else 0
        history = self.data_provider.get_history(
            symbol=symbol,
            start_date=self.config.data.start_date,
            end_date=self.config.data.end_date,
            adjust=self.config.data.adjust,
        )
        return self.strategy.generate_signal(symbol, history, position_size)

    def build_order_request(self, decision: SignalDecision) -> OrderRequest | None:
        if decision.signal == Signal.HOLD:
            return None

        snapshot = self.data_provider.get_realtime_snapshot([decision.symbol])
        if snapshot.empty:
            return None

        row = snapshot.iloc[0]
        last_price = float(row["last_price"])
        volume = self._resolve_trade_volume(decision.symbol, decision.signal, last_price)
        if volume <= 0:
            return None

        return OrderRequest(
            symbol=decision.symbol,
            side=decision.signal,
            price=last_price,
            volume=volume,
            note=decision.reason,
        )

    def execute_signal(self, decision: SignalDecision) -> OrderResult:
        request = self.build_order_request(decision)
        if request is None:
            if decision.signal == Signal.HOLD:
                return OrderResult(accepted=False, message="当前无交易信号")
            return OrderResult(accepted=False, message="下单数量为 0、无实时行情或持仓不足")

        if self.config.risk.dry_run:
            return OrderResult(
                accepted=True,
                message=f"Dry Run: {request.side.value} {request.symbol} {request.volume} @ {request.price:.2f}",
                order_id="DRY-RUN",
            )

        return self.broker.place_order(request)

    def _resolve_trade_volume(self, symbol: str, side: Signal, last_price: float) -> int:
        positions = {position.symbol: position for position in self.broker.get_positions()}
        trade_size = self.config.strategy.trade_size
        if side == Signal.SELL:
            position = positions.get(symbol)
            return position.available_volume if position else 0

        account = self.broker.get_account()
        budget = account.equity * self.config.risk.max_position_pct
        quantity = min(int(budget // last_price // 100 * 100), trade_size)
        return max(quantity, 0)
