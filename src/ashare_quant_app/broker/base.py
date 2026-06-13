from __future__ import annotations

from abc import ABC, abstractmethod

from ashare_quant_app.models import AccountSnapshot, OrderRequest, OrderResult, Position


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
