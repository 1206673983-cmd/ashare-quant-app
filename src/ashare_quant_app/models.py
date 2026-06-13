from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Signal(str, Enum):
    HOLD = "hold"
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIAL = "partial"


class EventLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class OrderRequest:
    symbol: str
    side: Signal
    price: float
    volume: int
    note: str = ""


@dataclass(slots=True)
class OrderResult:
    accepted: bool
    message: str
    order_id: str | None = None
    status: OrderStatus | None = None
    trade_id: str | None = None


@dataclass(slots=True)
class BrokerOrder:
    order_id: str
    symbol: str
    side: Signal
    price: float
    volume: int
    filled_volume: int
    status: OrderStatus
    message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class TradeFill:
    trade_id: str
    order_id: str
    symbol: str
    side: Signal
    price: float
    volume: int
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class BrokerEvent:
    level: EventLevel
    category: str
    message: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class Position:
    symbol: str
    volume: int
    available_volume: int
    avg_price: float
    last_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.volume * self.last_price


@dataclass(slots=True)
class AccountSnapshot:
    cash: float
    equity: float
    market_value: float
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class SignalDecision:
    symbol: str
    signal: Signal
    reason: str
    reference_price: float
    created_at: datetime = field(default_factory=datetime.now)
