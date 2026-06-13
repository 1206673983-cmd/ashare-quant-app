from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3

import pandas as pd

from ashare_quant_app.engine.backtest import BacktestResult
from ashare_quant_app.models import OrderResult, SignalDecision


@dataclass(slots=True)
class BacktestRecord:
    symbol: str
    strategy_name: str
    fast_window: int
    slow_window: int
    trade_size: int
    start_date: str
    end_date: str
    result: BacktestResult


@dataclass(slots=True)
class OrderRecord:
    symbol: str
    side: str
    price: float
    volume: int
    reason: str
    mode: str
    result: OrderResult
    created_at: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Storage:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS backtests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    fast_window INTEGER NOT NULL,
                    slow_window INTEGER NOT NULL,
                    trade_size INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    total_return REAL NOT NULL,
                    annual_return REAL NOT NULL,
                    max_drawdown REAL NOT NULL,
                    sharpe REAL NOT NULL,
                    trades INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    reference_price REAL NOT NULL,
                    reason TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    accepted INTEGER NOT NULL,
                    order_id TEXT,
                    message TEXT NOT NULL
                );
                """
            )

    def save_backtest(self, record: BacktestRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO backtests (
                    created_at, symbol, strategy_name, fast_window, slow_window, trade_size,
                    start_date, end_date, total_return, annual_return, max_drawdown, sharpe, trades
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    record.symbol,
                    record.strategy_name,
                    record.fast_window,
                    record.slow_window,
                    record.trade_size,
                    record.start_date,
                    record.end_date,
                    record.result.total_return,
                    record.result.annual_return,
                    record.result.max_drawdown,
                    record.result.sharpe,
                    record.result.trades,
                ),
            )

    def save_signal(self, decision: SignalDecision) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO signals (created_at, symbol, signal, reference_price, reason)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    decision.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    decision.symbol,
                    decision.signal.value,
                    decision.reference_price,
                    decision.reason,
                ),
            )

    def save_order(self, record: OrderRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO orders (
                    created_at, symbol, side, price, volume, reason, mode, accepted, order_id, message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.created_at,
                    record.symbol,
                    record.side,
                    record.price,
                    record.volume,
                    record.reason,
                    record.mode,
                    int(record.result.accepted),
                    record.result.order_id,
                    record.result.message,
                ),
            )

    def list_backtests(self, limit: int = 50) -> pd.DataFrame:
        return self._query_dataframe(
            """
            SELECT created_at, symbol, strategy_name, fast_window, slow_window, trade_size,
                   total_return, annual_return, max_drawdown, sharpe, trades
            FROM backtests
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def list_orders(self, limit: int = 50) -> pd.DataFrame:
        return self._query_dataframe(
            """
            SELECT created_at, symbol, side, price, volume, mode, accepted, order_id, message
            FROM orders
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def list_signals(self, limit: int = 50) -> pd.DataFrame:
        return self._query_dataframe(
            """
            SELECT created_at, symbol, signal, reference_price, reason
            FROM signals
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def _query_dataframe(self, query: str, params: tuple) -> pd.DataFrame:
        with self._connect() as connection:
            cursor = connection.execute(query, params)
            rows = cursor.fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(row) for row in rows])
