from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ashare_quant_app.models import Signal
from ashare_quant_app.strategies.base import Strategy


@dataclass(slots=True)
class BacktestResult:
    symbol: str
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe: float
    trades: int
    equity_curve: pd.DataFrame
    trade_log: pd.DataFrame


class BacktestEngine:
    def __init__(
        self,
        strategy: Strategy,
        initial_cash: float = 1_000_000,
        trade_size: int = 100,
        commission_rate: float = 0.0003,
    ) -> None:
        self.strategy = strategy
        self.initial_cash = float(initial_cash)
        self.trade_size = trade_size
        self.commission_rate = commission_rate

    def run(self, symbol: str, history: pd.DataFrame) -> BacktestResult:
        cash = self.initial_cash
        position = 0
        trades: list[dict] = []
        equity_rows: list[dict] = []

        for end_index in range(2, len(history) + 1):
            window = history.iloc[:end_index].copy()
            bar = window.iloc[-1]
            close_price = float(bar["close"])
            signal = self.strategy.generate_signal(symbol, window, position)

            if signal.signal == Signal.BUY and position == 0:
                shares = self.trade_size
                gross_cost = close_price * shares
                fee = gross_cost * self.commission_rate
                if gross_cost + fee <= cash:
                    cash -= gross_cost + fee
                    position += shares
                    trades.append(
                        {
                            "date": bar["date"],
                            "symbol": symbol,
                            "side": "buy",
                            "price": close_price,
                            "volume": shares,
                            "fee": fee,
                            "reason": signal.reason,
                        }
                    )
            elif signal.signal == Signal.SELL and position > 0:
                gross_value = close_price * position
                fee = gross_value * self.commission_rate
                trades.append(
                    {
                        "date": bar["date"],
                        "symbol": symbol,
                        "side": "sell",
                        "price": close_price,
                        "volume": position,
                        "fee": fee,
                        "reason": signal.reason,
                    }
                )
                cash += gross_value - fee
                position = 0

            equity = cash + position * close_price
            equity_rows.append(
                {
                    "date": bar["date"],
                    "equity": equity,
                    "cash": cash,
                    "position": position,
                    "close": close_price,
                }
            )

        equity_curve = pd.DataFrame(equity_rows)
        if equity_curve.empty:
            raise ValueError("无可回测的数据")

        equity_curve["returns"] = equity_curve["equity"].pct_change().fillna(0.0)
        equity_curve["cummax"] = equity_curve["equity"].cummax()
        equity_curve["drawdown"] = equity_curve["equity"] / equity_curve["cummax"] - 1.0

        total_return = equity_curve["equity"].iloc[-1] / self.initial_cash - 1.0
        trading_days = max(len(equity_curve), 1)
        annual_return = (1 + total_return) ** (252 / trading_days) - 1 if trading_days > 1 else total_return
        volatility = equity_curve["returns"].std()
        sharpe = 0.0 if volatility == 0 or pd.isna(volatility) else (equity_curve["returns"].mean() / volatility) * (252 ** 0.5)

        return BacktestResult(
            symbol=symbol,
            total_return=total_return,
            annual_return=annual_return,
            max_drawdown=float(equity_curve["drawdown"].min()),
            sharpe=float(sharpe),
            trades=len(trades),
            equity_curve=equity_curve,
            trade_log=pd.DataFrame(trades),
        )
