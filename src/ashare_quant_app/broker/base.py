from __future__ import annotations

from abc import ABC, abstractmethod

from ashare_quant_app.models import (
    AccountSnapshot,
    BrokerEvent,
    BrokerOrder,
    OrderRequest,
    OrderResult,
    Position,
    TradeFill,
)


class Broker(ABC):
    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_account(self) -> AccountSnapshot:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> list[Position]:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, request: OrderRequest) -> OrderResult:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> OrderResult:
        raise NotImplementedError

    @abstractmethod
    def get_orders(self) -> list[BrokerOrder]:
        raise NotImplementedError

    @abstractmethod
    def get_trades(self) -> list[TradeFill]:
        raise NotImplementedError

    @abstractmethod
    def get_events(self) -> list[BrokerEvent]:
        raise NotImplementedError
