from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import akshare as ak
import pandas as pd


def normalize_symbol(symbol: str) -> str:
    return symbol.split(".")[0].strip()


class DataProvider(ABC):
    @abstractmethod
    def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def get_realtime_snapshot(self, symbols: list[str]) -> pd.DataFrame:
        raise NotImplementedError


class AkshareDataProvider(DataProvider):
    def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        code = normalize_symbol(symbol)
        history = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust=adjust,
        )
        renamed = history.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "turnover",
                "振幅": "amplitude",
                "涨跌幅": "pct_change",
            }
        )
        renamed["date"] = pd.to_datetime(renamed["date"])
        renamed["symbol"] = code
        return renamed.sort_values("date").reset_index(drop=True)

    def get_realtime_snapshot(self, symbols: list[str]) -> pd.DataFrame:
        wanted = {normalize_symbol(symbol) for symbol in symbols}
        spot = ak.stock_zh_a_spot_em()
        renamed = spot.rename(
            columns={
                "代码": "symbol",
                "名称": "name",
                "最新价": "last_price",
                "涨跌幅": "pct_change",
                "成交量": "volume",
                "成交额": "turnover",
                "最高": "high",
                "最低": "low",
                "今开": "open",
                "昨收": "pre_close",
            }
        )
        filtered = renamed[renamed["symbol"].isin(wanted)].copy()
        filtered["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return filtered.reset_index(drop=True)
