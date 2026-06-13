from __future__ import annotations

import pandas as pd
from PySide6.QtCharts import (
    QCandlestickSeries,
    QCandlestickSet,
    QChart,
    QChartView,
    QLineSeries,
    QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter


class BaseChartView(QChartView):
    def __init__(self, title: str) -> None:
        chart = QChart()
        chart.setTitle(title)
        super().__init__(chart)
        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(280)


class PriceChartView(BaseChartView):
    def __init__(self) -> None:
        super().__init__("价格与均线")

    def update_history(self, history: pd.DataFrame, fast_window: int, slow_window: int) -> None:
        chart = QChart()
        chart.setTitle("价格与均线")
        chart.legend().setVisible(True)

        if history.empty:
            self.setChart(chart)
            return

        frame = history.tail(80).copy().reset_index(drop=True)
        frame["fast_ma"] = frame["close"].rolling(fast_window).mean()
        frame["slow_ma"] = frame["close"].rolling(slow_window).mean()

        candle_series = QCandlestickSeries()
        candle_series.setName("K线")
        candle_series.setIncreasingColor(Qt.GlobalColor.red)
        candle_series.setDecreasingColor(Qt.GlobalColor.green)

        fast_series = QLineSeries()
        fast_series.setName(f"MA{fast_window}")

        slow_series = QLineSeries()
        slow_series.setName(f"MA{slow_window}")

        for index, row in frame.iterrows():
            candle = QCandlestickSet(float(index))
            candle.setOpen(float(row["open"]))
            candle.setHigh(float(row["high"]))
            candle.setLow(float(row["low"]))
            candle.setClose(float(row["close"]))
            candle_series.append(candle)
            if not pd.isna(row["fast_ma"]):
                fast_series.append(float(index), float(row["fast_ma"]))
            if not pd.isna(row["slow_ma"]):
                slow_series.append(float(index), float(row["slow_ma"]))

        chart.addSeries(candle_series)
        chart.addSeries(fast_series)
        chart.addSeries(slow_series)

        x_axis = QValueAxis()
        x_axis.setLabelFormat("%.0f")
        x_axis.setTickCount(min(len(frame), 8))
        x_axis.setTitleText("最近交易日序号")

        min_price = float(frame["low"].min()) * 0.98
        max_price = float(frame["high"].max()) * 1.02
        y_axis = QValueAxis()
        y_axis.setRange(min_price, max_price)
        y_axis.setLabelFormat("%.2f")
        y_axis.setTitleText("价格")

        chart.addAxis(x_axis, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(y_axis, Qt.AlignmentFlag.AlignLeft)

        for series in (candle_series, fast_series, slow_series):
            series.attachAxis(x_axis)
            series.attachAxis(y_axis)
        self.setChart(chart)


class EquityChartView(BaseChartView):
    def __init__(self) -> None:
        super().__init__("权益曲线")

    def update_equity_curve(self, equity_curve: pd.DataFrame) -> None:
        chart = QChart()
        chart.setTitle("权益曲线")
        chart.legend().setVisible(True)

        if equity_curve.empty:
            self.setChart(chart)
            return

        frame = equity_curve.tail(120).reset_index(drop=True)
        equity_series = QLineSeries()
        equity_series.setName("Equity")
        drawdown_series = QLineSeries()
        drawdown_series.setName("Drawdown")

        for index, row in frame.iterrows():
            equity_series.append(float(index), float(row["equity"]))
            drawdown_series.append(float(index), float(row.get("drawdown", 0.0) * 100))

        price_axis = QValueAxis()
        price_axis.setLabelFormat("%.0f")
        price_axis.setTitleText("资产")
        price_axis.setRange(float(frame["equity"].min()) * 0.995, float(frame["equity"].max()) * 1.005)

        x_axis = QValueAxis()
        x_axis.setLabelFormat("%.0f")
        x_axis.setTickCount(min(len(frame), 8))
        x_axis.setTitleText("回测步数")

        dd_axis = QValueAxis()
        dd_axis.setLabelFormat("%.2f%%")
        dd_axis.setTitleText("回撤")
        dd_axis.setRange(float(frame.get("drawdown", pd.Series([0.0])).min() * 100), 0.0)

        chart.addSeries(equity_series)
        chart.addSeries(drawdown_series)
        chart.addAxis(x_axis, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(price_axis, Qt.AlignmentFlag.AlignLeft)
        chart.addAxis(dd_axis, Qt.AlignmentFlag.AlignRight)

        equity_series.attachAxis(x_axis)
        equity_series.attachAxis(price_axis)
        drawdown_series.attachAxis(x_axis)
        drawdown_series.attachAxis(dd_axis)
        self.setChart(chart)
