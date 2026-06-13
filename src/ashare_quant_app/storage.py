from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3

import pandas as pd

from ashare_quant_app.engine.backtest import BacktestResult
from ashare_quant_app.models import (
    AccountSnapshot,
    BrokerEvent,
    BrokerOrder,
    OrderResult,
    Position,
    SignalDecision,
    TradeFill,
)


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


@dataclass(slots=True)
class AccountSnapshotRecord:
    account: AccountSnapshot
    source: str
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
                    status TEXT,
                    trade_id TEXT,
                    message TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS broker_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    captured_at TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    filled_volume INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    captured_at TEXT NOT NULL,
                    trade_id TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS account_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    cash REAL NOT NULL,
                    equity REAL NOT NULL,
                    market_value REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS position_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    volume INTEGER NOT NULL,
                    available_volume INTEGER NOT NULL,
                    avg_price REAL NOT NULL,
                    last_price REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS broker_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    level TEXT NOT NULL,
                    category TEXT NOT NULL,
                    message TEXT NOT NULL
                );
                """
            )
            self._ensure_column(connection, "orders", "status", "TEXT")
            self._ensure_column(connection, "orders", "trade_id", "TEXT")

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
                    created_at, symbol, side, price, volume, reason, mode, accepted, order_id, status, trade_id, message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    record.result.status.value if record.result.status else None,
                    record.result.trade_id,
                    record.result.message,
                ),
            )

    def save_broker_orders(self, orders: list[BrokerOrder]) -> None:
        if not orders:
            return
        captured_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
            connection.executemany(
                "DELETE FROM broker_orders WHERE order_id = ?",
                [(order.order_id,) for order in orders],
            )
            connection.executemany(
                """
                INSERT INTO broker_orders (
                    captured_at, order_id, symbol, side, price, volume, filled_volume, status, message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        captured_at,
                        order.order_id,
                        order.symbol,
                        order.side.value,
                        order.price,
                        order.volume,
                        order.filled_volume,
                        order.status.value,
                        order.message,
                        order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        order.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                    for order in orders
                ],
            )

    def save_trades(self, trades: list[TradeFill]) -> None:
        if not trades:
            return
        captured_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
            connection.executemany(
                "DELETE FROM trades WHERE trade_id = ?",
                [(trade.trade_id,) for trade in trades],
            )
            connection.executemany(
                """
                INSERT INTO trades (
                    captured_at, trade_id, order_id, symbol, side, price, volume, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        captured_at,
                        trade.trade_id,
                        trade.order_id,
                        trade.symbol,
                        trade.side.value,
                        trade.price,
                        trade.volume,
                        trade.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                    for trade in trades
                ],
            )

    def save_account_snapshot(self, record: AccountSnapshotRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO account_snapshots (created_at, source, cash, equity, market_value)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.created_at,
                    record.source,
                    record.account.cash,
                    record.account.equity,
                    record.account.market_value,
                ),
            )

    def save_position_snapshot(self, positions: list[Position], source: str) -> None:
        if not positions:
            return
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO position_snapshots (
                    created_at, source, symbol, volume, available_volume, avg_price, last_price
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        created_at,
                        source,
                        position.symbol,
                        position.volume,
                        position.available_volume,
                        position.avg_price,
                        position.last_price,
                    )
                    for position in positions
                ],
            )

    def save_events(self, events: list[BrokerEvent]) -> None:
        if not events:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO broker_events (created_at, level, category, message)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        event.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        event.level.value,
                        event.category,
                        event.message,
                    )
                    for event in events
                ],
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
            SELECT created_at, symbol, side, price, volume, mode, accepted, order_id, status, trade_id, message
            FROM orders
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def list_broker_orders(self, limit: int = 100) -> pd.DataFrame:
        return self._query_dataframe(
            """
            SELECT captured_at, order_id, symbol, side, price, volume, filled_volume, status, message
            FROM broker_orders
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def list_trades(self, limit: int = 100) -> pd.DataFrame:
        return self._query_dataframe(
            """
            SELECT captured_at, trade_id, order_id, symbol, side, price, volume, created_at
            FROM trades
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

    def list_account_snapshots(self, limit: int = 50) -> pd.DataFrame:
        return self._query_dataframe(
            """
            SELECT created_at, source, cash, equity, market_value
            FROM account_snapshots
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def list_position_snapshots(self, limit: int = 100) -> pd.DataFrame:
        return self._query_dataframe(
            """
            SELECT created_at, source, symbol, volume, available_volume, avg_price, last_price
            FROM position_snapshots
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def list_events(self, limit: int = 100) -> pd.DataFrame:
        return self._query_dataframe(
            """
            SELECT created_at, level, category, message
            FROM broker_events
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

    def _ensure_column(self, connection: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
