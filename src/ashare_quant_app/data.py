from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
import math

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
    def __init__(self, realtime_provider: str = "auto") -> None:
        self.realtime_provider = realtime_provider

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
        easyquotation_snapshot = self._try_easyquotation_snapshot(sorted(wanted))
        if not easyquotation_snapshot.empty:
            return easyquotation_snapshot

        try:
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
            filtered["data_source"] = "realtime"
            return filtered.reset_index(drop=True)
        except Exception:
            try:
                return self._build_history_fallback_snapshot(sorted(wanted))
            except Exception:
                return self._build_offline_snapshot(sorted(wanted))

    def _build_history_fallback_snapshot(self, symbols: list[str]) -> pd.DataFrame:
        rows: list[dict] = []
        fallback_end = datetime.now().strftime("%Y%m%d")
        fallback_start = "20220101"

        for symbol in symbols:
            history = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=fallback_start,
                end_date=fallback_end,
                adjust="qfq",
            )
            if history.empty:
                continue
            latest = history.iloc[-1]
            last_price = float(latest["收盘"])
            pre_close = float(history.iloc[-2]["收盘"]) if len(history) > 1 else last_price
            pct_change = 0.0 if pre_close == 0 else ((last_price / pre_close) - 1.0) * 100
            rows.append(
                {
                    "symbol": symbol,
                    "name": symbol,
                    "last_price": last_price,
                    "pct_change": pct_change if not math.isnan(pct_change) else 0.0,
                    "volume": int(latest.get("成交量", 0) or 0),
                    "turnover": float(latest.get("成交额", 0.0) or 0.0),
                    "high": float(latest.get("最高", last_price) or last_price),
                    "low": float(latest.get("最低", last_price) or last_price),
                    "open": float(latest.get("开盘", last_price) or last_price),
                    "pre_close": pre_close,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "data_source": "history_fallback",
                }
            )

        return pd.DataFrame(rows)

    def _build_offline_snapshot(self, symbols: list[str]) -> pd.DataFrame:
        rows: list[dict] = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for index, symbol in enumerate(symbols):
            # Deterministic local fallback so the simulator can run fully offline.
            base_price = 10.0 + index * 5.0
            rows.append(
                {
                    "symbol": symbol,
                    "name": f"{symbol}-offline",
                    "last_price": base_price,
                    "pct_change": 0.0,
                    "volume": 0,
                    "turnover": 0.0,
                    "high": round(base_price * 1.01, 2),
                    "low": round(base_price * 0.99, 2),
                    "open": base_price,
                    "pre_close": base_price,
                    "updated_at": now,
                    "data_source": "offline_fallback",
                }
            )
        return pd.DataFrame(rows)

    def _try_easyquotation_snapshot(self, symbols: list[str]) -> pd.DataFrame:
        if self.realtime_provider not in {"auto", "easyquotation"}:
            return pd.DataFrame()
        try:
            import easyquotation
        except ImportError:
            return pd.DataFrame()

        for source_name in ("sina", "tencent"):
            try:
                quotation = easyquotation.use(source_name)
                raw = quotation.real(symbols)
                rows = []
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for symbol in symbols:
                    item = raw.get(symbol)
                    if not item:
                        continue
                    last_price = float(item.get("now") or item.get("close") or 0.0)
                    pre_close = float(item.get("close") or last_price or 0.0)
                    rows.append(
                        {
                            "symbol": symbol,
                            "name": item.get("name", symbol),
                            "last_price": last_price,
                            "pct_change": 0.0 if pre_close == 0 else ((last_price / pre_close) - 1.0) * 100,
                            "volume": int(float(item.get("volume", 0) or 0)),
                            "turnover": float(item.get("turnover", 0.0) or 0.0),
                            "high": float(item.get("high", last_price) or last_price),
                            "low": float(item.get("low", last_price) or last_price),
                            "open": float(item.get("open", last_price) or last_price),
                            "pre_close": pre_close,
                            "updated_at": now,
                            "data_source": f"easyquotation_{source_name}",
                        }
                    )
                if rows:
                    return pd.DataFrame(rows)
            except Exception:
                continue
        return pd.DataFrame()
