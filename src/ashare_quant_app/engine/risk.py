from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from ashare_quant_app.config import RiskConfig
from ashare_quant_app.models import Position, Signal, SignalDecision


class RiskManager:
    def __init__(self, config: RiskConfig) -> None:
        self.config = config
        self._trade_history: dict[str, list[datetime]] = defaultdict(list)

    def refresh_config(self, config: RiskConfig) -> None:
        self.config = config

    def maybe_force_exit(self, symbol: str, position: Position | None, last_price: float) -> SignalDecision | None:
        if position is None or position.volume <= 0 or position.avg_price <= 0:
            return None

        stop_loss_price = position.avg_price * (1 - self.config.stop_loss_pct)
        take_profit_price = position.avg_price * (1 + self.config.take_profit_pct)

        if self.config.stop_loss_pct > 0 and last_price <= stop_loss_price:
            return SignalDecision(
                symbol=symbol,
                signal=Signal.SELL,
                reason=f"触发止损: 当前价 {last_price:.2f} <= 止损价 {stop_loss_price:.2f}",
                reference_price=last_price,
            )

        if self.config.take_profit_pct > 0 and last_price >= take_profit_price:
            return SignalDecision(
                symbol=symbol,
                signal=Signal.SELL,
                reason=f"触发止盈: 当前价 {last_price:.2f} >= 止盈价 {take_profit_price:.2f}",
                reference_price=last_price,
            )

        return None

    def validate_order(self, symbol: str, side: Signal) -> str | None:
        if side == Signal.SELL:
            return None
        self._cleanup_old_trades()
        if self.config.max_daily_trades > 0 and len(self._trade_history[symbol]) >= self.config.max_daily_trades:
            return f"触发风控: {symbol} 当日交易次数达到上限 {self.config.max_daily_trades}"

        if self.config.min_trade_interval_seconds > 0 and self._trade_history[symbol]:
            elapsed = (datetime.now() - self._trade_history[symbol][-1]).total_seconds()
            if elapsed < self.config.min_trade_interval_seconds:
                return (
                    f"触发风控: {symbol} 距离上次交易仅 {int(elapsed)} 秒，"
                    f"小于最小间隔 {self.config.min_trade_interval_seconds} 秒"
                )

        if side not in {Signal.BUY, Signal.SELL}:
            return "触发风控: 不支持的交易方向"

        return None

    def record_trade(self, symbol: str) -> None:
        self._trade_history[symbol].append(datetime.now())
        self._cleanup_old_trades()

    def _cleanup_old_trades(self) -> None:
        today = datetime.now().date()
        for symbol, timestamps in list(self._trade_history.items()):
            self._trade_history[symbol] = [item for item in timestamps if item.date() == today]
