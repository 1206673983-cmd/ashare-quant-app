from __future__ import annotations

from ashare_quant_app.broker.base import Broker
from ashare_quant_app.config import AppConfig
from ashare_quant_app.data import DataProvider
from ashare_quant_app.engine.risk import RiskManager
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
        self.risk_manager = RiskManager(config.risk)
        self.last_block_reason = ""

    def evaluate_symbol(self, symbol: str) -> SignalDecision:
        self.risk_manager.refresh_config(self.config.risk)
        positions = {position.symbol: position for position in self.broker.get_positions()}
        position = positions.get(symbol)
        position_size = position.available_volume if position else 0
        history = self.data_provider.get_history(
            symbol=symbol,
            start_date=self.config.data.start_date,
            end_date=self.config.data.end_date,
            adjust=self.config.data.adjust,
        )
        snapshot = self.data_provider.get_realtime_snapshot([symbol])
        if not snapshot.empty:
            forced_exit = self.risk_manager.maybe_force_exit(
                symbol=symbol,
                position=position,
                last_price=float(snapshot.iloc[0]["last_price"]),
            )
            if forced_exit is not None:
                return forced_exit
        return self.strategy.generate_signal(symbol, history, position_size)

    def build_order_request(self, decision: SignalDecision) -> OrderRequest | None:
        self.last_block_reason = ""
        if decision.signal == Signal.HOLD:
            self.last_block_reason = "当前无交易信号"
            return None

        snapshot = self.data_provider.get_realtime_snapshot([decision.symbol])
        if snapshot.empty:
            self.last_block_reason = "未获取到实时行情，无法下单"
            return None

        row = snapshot.iloc[0]
        last_price = float(row["last_price"])
        risk_message = self.risk_manager.validate_order(decision.symbol, decision.signal)
        if risk_message:
            self.last_block_reason = risk_message
            return None
        volume = self._resolve_trade_volume(decision.symbol, decision.signal, last_price)
        if volume <= 0:
            self.last_block_reason = "下单数量为 0，请检查现金或持仓"
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
            return OrderResult(accepted=False, message=self.last_block_reason or "交易请求被拦截")

        if self.config.risk.dry_run:
            result = self.broker.place_order(request)
            result.message = f"Dry Run: {result.message}"
        else:
            result = self.broker.place_order(request)

        if result.accepted:
            self.risk_manager.record_trade(decision.symbol)

        return result

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
