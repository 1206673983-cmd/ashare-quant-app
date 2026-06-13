from __future__ import annotations

import pandas as pd

from ashare_quant_app.data import AkshareDataProvider


def test_realtime_snapshot_falls_back_to_history(monkeypatch) -> None:
    provider = AkshareDataProvider()

    def raise_realtime_error():
        raise ConnectionError("remote disconnected")

    def fake_history(symbol: str, period: str, start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"开盘": 9.8, "收盘": 10.0, "最高": 10.1, "最低": 9.7, "成交量": 1000, "成交额": 10000},
                {"开盘": 10.0, "收盘": 10.5, "最高": 10.6, "最低": 9.9, "成交量": 1200, "成交额": 12600},
            ]
        )

    monkeypatch.setattr("ashare_quant_app.data.ak.stock_zh_a_spot_em", raise_realtime_error)
    monkeypatch.setattr("ashare_quant_app.data.ak.stock_zh_a_hist", fake_history)

    snapshot = provider.get_realtime_snapshot(["600519"])

    assert len(snapshot) == 1
    assert snapshot.iloc[0]["symbol"] == "600519"
    assert snapshot.iloc[0]["data_source"] == "history_fallback"
    assert snapshot.iloc[0]["last_price"] == 10.5


def test_realtime_snapshot_falls_back_to_offline_when_all_remote_sources_fail(monkeypatch) -> None:
    provider = AkshareDataProvider()

    def raise_realtime_error():
        raise ConnectionError("remote disconnected")

    def raise_history_error(symbol: str, period: str, start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
        raise ConnectionError("history disconnected")

    monkeypatch.setattr("ashare_quant_app.data.ak.stock_zh_a_spot_em", raise_realtime_error)
    monkeypatch.setattr("ashare_quant_app.data.ak.stock_zh_a_hist", raise_history_error)

    snapshot = provider.get_realtime_snapshot(["600519"])

    assert len(snapshot) == 1
    assert snapshot.iloc[0]["symbol"] == "600519"
    assert snapshot.iloc[0]["data_source"] == "offline_fallback"
