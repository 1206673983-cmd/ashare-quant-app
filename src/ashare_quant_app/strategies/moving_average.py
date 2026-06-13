from __future__ import annotations

import pandas as pd

from ashare_quant_app.models import Signal, SignalDecision
from ashare_quant_app.strategies.base import Strategy


class MovingAverageCrossStrategy(Strategy):
    def __init__(self, fast_window: int = 5, slow_window: int = 20) -> None:
        if fast_window >= slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        self.fast_window = fast_window
        self.slow_window = slow_window

    def generate_signal(self, symbol: str, history: pd.DataFrame, position_size: int) -> SignalDecision:
        if len(history) < self.slow_window + 1:
            last_price = float(history["close"].iloc[-1]) if not history.empty else 0.0
            return SignalDecision(
                symbol=symbol,
                signal=Signal.HOLD,
                reason="历史数据不足，无法生成均线信号",
                reference_price=last_price,
            )

        frame = history.copy()
        frame["fast_ma"] = frame["close"].rolling(self.fast_window).mean()
        frame["slow_ma"] = frame["close"].rolling(self.slow_window).mean()

        prev = frame.iloc[-2]
        curr = frame.iloc[-1]
        last_price = float(curr["close"])

        golden_cross = prev["fast_ma"] <= prev["slow_ma"] and curr["fast_ma"] > curr["slow_ma"]
        death_cross = prev["fast_ma"] >= prev["slow_ma"] and curr["fast_ma"] < curr["slow_ma"]

        if golden_cross and position_size <= 0:
            return SignalDecision(
                symbol=symbol,
                signal=Signal.BUY,
                reason=f"快线({self.fast_window})上穿慢线({self.slow_window})",
                reference_price=last_price,
            )

        if death_cross and position_size > 0:
            return SignalDecision(
                symbol=symbol,
                signal=Signal.SELL,
                reason=f"快线({self.fast_window})下穿慢线({self.slow_window})",
                reference_price=last_price,
            )

        return SignalDecision(
            symbol=symbol,
            signal=Signal.HOLD,
            reason="当前无开平仓信号",
            reference_price=last_price,
        )
