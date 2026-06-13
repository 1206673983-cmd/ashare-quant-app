from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ashare_quant_app.broker import SimulatedBroker, XtQuantBroker
from ashare_quant_app.config import AppConfig
from ashare_quant_app.data import AkshareDataProvider
from ashare_quant_app.engine import BacktestEngine, LiveTradingEngine
from ashare_quant_app.models import Position
from ashare_quant_app.strategies import MovingAverageCrossStrategy


class MainWindow(QMainWindow):
    def __init__(self, config_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("A股量化交易终端")
        self.resize(1280, 820)

        default_config = config_path or str(Path.cwd() / "config.example.toml")
        self.config_path = default_config
        self.config = AppConfig()
        self.data_provider = AkshareDataProvider()
        self.broker = SimulatedBroker()
        self.broker.connect()
        self.live_engine: LiveTradingEngine | None = None

        self._build_ui()
        self.config_path_edit.setText(self.config_path)
        self.load_config()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        layout.addWidget(self._build_control_panel())
        layout.addWidget(self._build_status_panel())
        layout.addWidget(self._build_market_panel())
        layout.addWidget(self._build_log_panel())

        self.setCentralWidget(root)

    def _build_control_panel(self) -> QGroupBox:
        box = QGroupBox("控制台")
        grid = QGridLayout(box)

        self.config_path_edit = QLineEdit()
        browse_btn = QPushButton("选择配置")
        load_btn = QPushButton("加载配置")
        browse_btn.clicked.connect(self._choose_config)
        load_btn.clicked.connect(self.load_config)

        self.symbol_combo = QComboBox()
        backtest_btn = QPushButton("运行回测")
        signal_btn = QPushButton("评估信号")
        execute_btn = QPushButton("执行信号")
        quote_btn = QPushButton("刷新行情")
        position_btn = QPushButton("刷新持仓")

        backtest_btn.clicked.connect(self.run_backtest)
        signal_btn.clicked.connect(self.evaluate_signal)
        execute_btn.clicked.connect(self.execute_signal)
        quote_btn.clicked.connect(self.refresh_market)
        position_btn.clicked.connect(self.refresh_positions)

        grid.addWidget(QLabel("配置文件"), 0, 0)
        grid.addWidget(self.config_path_edit, 0, 1, 1, 4)
        grid.addWidget(browse_btn, 0, 5)
        grid.addWidget(load_btn, 0, 6)

        grid.addWidget(QLabel("交易标的"), 1, 0)
        grid.addWidget(self.symbol_combo, 1, 1, 1, 2)
        grid.addWidget(backtest_btn, 1, 3)
        grid.addWidget(signal_btn, 1, 4)
        grid.addWidget(execute_btn, 1, 5)
        grid.addWidget(quote_btn, 1, 6)
        grid.addWidget(position_btn, 1, 7)
        return box

    def _build_status_panel(self) -> QGroupBox:
        box = QGroupBox("运行状态")
        row = QHBoxLayout(box)

        self.mode_label = QLabel("模式: -")
        self.strategy_label = QLabel("策略: -")
        self.account_label = QLabel("账户: -")
        self.signal_label = QLabel("最近信号: -")

        row.addWidget(self.mode_label)
        row.addWidget(self.strategy_label)
        row.addWidget(self.account_label)
        row.addWidget(self.signal_label)
        return box

    def _build_market_panel(self) -> QGroupBox:
        box = QGroupBox("行情与持仓")
        row = QHBoxLayout(box)

        self.quote_table = QTableWidget(0, 6)
        self.quote_table.setHorizontalHeaderLabels(["代码", "名称", "最新价", "涨跌幅", "成交量", "更新时间"])

        self.position_table = QTableWidget(0, 5)
        self.position_table.setHorizontalHeaderLabels(["代码", "数量", "可用", "成本价", "最新价"])

        row.addWidget(self.quote_table)
        row.addWidget(self.position_table)
        return box

    def _build_log_panel(self) -> QGroupBox:
        box = QGroupBox("日志")
        layout = QVBoxLayout(box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        return box

    def _choose_config(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(self, "选择配置文件", self.config_path, "TOML Files (*.toml)")
        if chosen:
            self.config_path_edit.setText(chosen)

    def load_config(self) -> None:
        try:
            config_path = Path(self.config_path_edit.text().strip())
            self.config = AppConfig.from_file(config_path) if config_path.exists() else AppConfig()
            self.config_path = str(config_path)
            self._refresh_runtime()
            self.symbol_combo.clear()
            self.symbol_combo.addItems(self.config.data.default_symbols)
            mode = "QMT 实盘" if self.config.xtquant.enabled and not self.config.risk.dry_run else "本地 Dry Run"
            self.mode_label.setText(f"模式: {mode}")
            self.strategy_label.setText(
                f"策略: 双均线 {self.config.strategy.fast_window}/{self.config.strategy.slow_window}"
            )
            self.log(f"加载配置成功: {self.config_path}")
            self.refresh_positions()
            self.refresh_market()
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("加载配置失败", str(exc))

    def _refresh_runtime(self) -> None:
        strategy = MovingAverageCrossStrategy(
            fast_window=self.config.strategy.fast_window,
            slow_window=self.config.strategy.slow_window,
        )
        if self.config.xtquant.enabled and not self.config.risk.dry_run:
            self.broker = XtQuantBroker(self.config.xtquant)
            self.broker.connect()
        else:
            self.broker = SimulatedBroker()
            self.broker.connect()
        self.live_engine = LiveTradingEngine(strategy, self.data_provider, self.broker, self.config)

    def run_backtest(self) -> None:
        try:
            symbol = self._current_symbol()
            strategy = MovingAverageCrossStrategy(
                fast_window=self.config.strategy.fast_window,
                slow_window=self.config.strategy.slow_window,
            )
            history = self.data_provider.get_history(
                symbol=symbol,
                start_date=self.config.data.start_date,
                end_date=self.config.data.end_date,
                adjust=self.config.data.adjust,
            )
            engine = BacktestEngine(strategy=strategy, trade_size=self.config.strategy.trade_size)
            result = engine.run(symbol, history)
            self.log(
                "回测完成 | "
                f"{symbol} | 总收益 {result.total_return:.2%} | 年化 {result.annual_return:.2%} | "
                f"最大回撤 {result.max_drawdown:.2%} | 夏普 {result.sharpe:.2f} | 交易次数 {result.trades}"
            )
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("回测失败", str(exc))

    def evaluate_signal(self) -> None:
        try:
            symbol = self._current_symbol()
            if self.live_engine is None:
                raise RuntimeError("交易引擎尚未初始化")
            decision = self.live_engine.evaluate_symbol(symbol)
            self.signal_label.setText(
                f"最近信号: {decision.signal.value.upper()} @ {decision.reference_price:.2f} | {decision.reason}"
            )
            self.log(
                f"信号评估完成 | {decision.symbol} | {decision.signal.value.upper()} | "
                f"{decision.reference_price:.2f} | {decision.reason}"
            )
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("信号评估失败", str(exc))

    def execute_signal(self) -> None:
        try:
            symbol = self._current_symbol()
            if self.live_engine is None:
                raise RuntimeError("交易引擎尚未初始化")
            decision = self.live_engine.evaluate_symbol(symbol)
            result = self.live_engine.execute_signal(decision)
            self.signal_label.setText(
                f"最近信号: {decision.signal.value.upper()} @ {decision.reference_price:.2f} | {result.message}"
            )
            self.log(f"执行结果 | {decision.symbol} | {result.message}")
            self.refresh_positions()
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("执行失败", str(exc))

    def refresh_market(self) -> None:
        try:
            symbols = [self.symbol_combo.itemText(i) for i in range(self.symbol_combo.count())]
            if not symbols:
                return
            snapshot = self.data_provider.get_realtime_snapshot(symbols)
            self.quote_table.setRowCount(len(snapshot))
            for row_idx, (_, row) in enumerate(snapshot.iterrows()):
                values = [
                    row.get("symbol", ""),
                    row.get("name", ""),
                    f'{float(row.get("last_price", 0.0)):.2f}',
                    f'{float(row.get("pct_change", 0.0)):.2f}%',
                    str(int(row.get("volume", 0))),
                    row.get("updated_at", ""),
                ]
                for col_idx, value in enumerate(values):
                    self.quote_table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
            self.log(f"刷新行情成功，共 {len(snapshot)} 条")
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("刷新行情失败", str(exc))

    def refresh_positions(self) -> None:
        try:
            positions = self.broker.get_positions()
            account = self.broker.get_account()
            self.account_label.setText(
                f"账户: 现金 {account.cash:,.2f} | 市值 {account.market_value:,.2f} | 总资产 {account.equity:,.2f}"
            )
            self.position_table.setRowCount(len(positions))
            for row_idx, position in enumerate(positions):
                self._populate_position_row(row_idx, position)
            self.log(f"刷新持仓成功，共 {len(positions)} 条")
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("刷新持仓失败", str(exc))

    def _populate_position_row(self, row_idx: int, position: Position) -> None:
        values = [
            position.symbol,
            str(position.volume),
            str(position.available_volume),
            f"{position.avg_price:.2f}",
            f"{position.last_price:.2f}",
        ]
        for col_idx, value in enumerate(values):
            self.position_table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _current_symbol(self) -> str:
        symbol = self.symbol_combo.currentText().strip()
        if not symbol:
            raise RuntimeError("请先选择交易标的")
        return symbol

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{timestamp}] {message}")

    def _show_error(self, title: str, message: str) -> None:
        self.log(f"{title}: {message}")
        QMessageBox.critical(self, title, message)
