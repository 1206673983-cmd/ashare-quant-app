from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from ashare_quant_app.models import SignalDecision


class Strategy(ABC):
    @abstractmethod
    def generate_signal(self, symbol: str, history: pd.DataFrame, position_size: int) -> SignalDecision:
        raise NotImplementedError
