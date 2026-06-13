from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ashare_quant_app.broker import SimulatedBroker, XtQuantBroker
from ashare_quant_app.config import AppConfig
from ashare_quant_app.data import AkshareDataProvider
from ashare_quant_app.engine import BacktestEngine, BacktestResult, LiveTradingEngine
from ashare_quant_app.models import Position, SignalDecision
from ashare_quant_app.storage import AccountSnapshotRecord, BacktestRecord, OrderRecord, Storage
from ashare_quant_app.strategies import MovingAverageCrossStrategy
from ashare_quant_app.ui.charts import EquityChartView, PriceChartView


class MainWindow(QMainWindow):
    def __init__(self, config_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("A股量化交易终端")
        self.resize(1480, 980)

        default_config = config_path or str(Path.cwd() / "config.example.toml")
        self.config_path = default_config
        self.config = AppConfig()
        self.storage = Storage(Path.cwd() / "data" / "ashare_quant_app.db")
        self.data_provider = AkshareDataProvider()
        self.broker = SimulatedBroker()
        self.broker.connect()
        self.live_engine: LiveTradingEngine | None = None
        self.last_decision: SignalDecision | None = None
        self.last_backtest_result: BacktestResult | None = None
        self.cancel_order_edit = QLineEdit()

        self._build_ui()
        self.config_path_edit.setText(self.config_path)
        self.load_config()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        layout.addWidget(self._build_control_panel())
        layout.addWidget(self._build_status_panel())
        layout.addWidget(self._build_workspace())
        layout.addWidget(self._build_records_panel())

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
        self.fast_window_spin = QSpinBox()
        self.fast_window_spin.setRange(2, 120)
        self.slow_window_spin = QSpinBox()
        self.slow_window_spin.setRange(3, 250)
        self.trade_size_spin = QSpinBox()
        self.trade_size_spin.setRange(100, 100000)
        self.trade_size_spin.setSingleStep(100)

        backtest_btn = QPushButton("运行回测")
        signal_btn = QPushButton("评估信号")
        execute_btn = QPushButton("执行信号")
        cancel_btn = QPushButton("撤销委托")
        quote_btn = QPushButton("刷新行情")
        position_btn = QPushButton("刷新持仓")
        refresh_record_btn = QPushButton("刷新记录")

        backtest_btn.clicked.connect(self.run_backtest)
        signal_btn.clicked.connect(self.evaluate_signal)
        execute_btn.clicked.connect(self.execute_signal)
        cancel_btn.clicked.connect(self.cancel_order)
        quote_btn.clicked.connect(self.refresh_market)
        position_btn.clicked.connect(self.refresh_positions)
        refresh_record_btn.clicked.connect(self.refresh_records)

        grid.addWidget(QLabel("配置文件"), 0, 0)
        grid.addWidget(self.config_path_edit, 0, 1, 1, 5)
        grid.addWidget(browse_btn, 0, 6)
        grid.addWidget(load_btn, 0, 7)

        grid.addWidget(QLabel("交易标的"), 1, 0)
        grid.addWidget(self.symbol_combo, 1, 1)
        grid.addWidget(QLabel("快线"), 1, 2)
        grid.addWidget(self.fast_window_spin, 1, 3)
        grid.addWidget(QLabel("慢线"), 1, 4)
        grid.addWidget(self.slow_window_spin, 1, 5)
        grid.addWidget(QLabel("每次交易股数"), 1, 6)
        grid.addWidget(self.trade_size_spin, 1, 7)

        grid.addWidget(QLabel("撤单订单号"), 2, 0)
        grid.addWidget(self.cancel_order_edit, 2, 1, 1, 2)
        grid.addWidget(cancel_btn, 2, 3)

        grid.addWidget(backtest_btn, 3, 1)
        grid.addWidget(signal_btn, 3, 2)
        grid.addWidget(execute_btn, 3, 3)
        grid.addWidget(quote_btn, 3, 4)
        grid.addWidget(position_btn, 3, 5)
        grid.addWidget(refresh_record_btn, 3, 6)
        return box

    def _build_status_panel(self) -> QGroupBox:
        box = QGroupBox("运行状态")
        row = QHBoxLayout(box)

        self.mode_label = QLabel("模式: -")
        self.strategy_label = QLabel("策略: -")
        self.storage_label = QLabel("数据库: -")
        self.account_label = QLabel("账户: -")
        self.signal_label = QLabel("最近信号: -")

        row.addWidget(self.mode_label)
        row.addWidget(self.strategy_label)
        row.addWidget(self.storage_label)
        row.addWidget(self.account_label)
        row.addWidget(self.signal_label)
        return box

    def _build_workspace(self) -> QWidget:
        splitter = QSplitter()

        left_box = QGroupBox("行情与持仓")
        left_layout = QVBoxLayout(left_box)
        self.quote_table = self._new_table(["代码", "名称", "最新价", "涨跌幅", "成交量", "更新时间"])
        self.position_table = self._new_table(["代码", "数量", "可用", "成本价", "最新价"])
        left_layout.addWidget(QLabel("实时行情"))
        left_layout.addWidget(self.quote_table)
        left_layout.addWidget(QLabel("当前持仓"))
        left_layout.addWidget(self.position_table)

        right_box = QGroupBox("图表分析")
        right_layout = QVBoxLayout(right_box)
        self.price_chart = PriceChartView()
        self.equity_chart = EquityChartView()
        right_layout.addWidget(self.price_chart)
        right_layout.addWidget(self.equity_chart)

        splitter.addWidget(left_box)
        splitter.addWidget(right_box)
        splitter.setSizes([650, 800])
        return splitter

    def _build_records_panel(self) -> QGroupBox:
        box = QGroupBox("记录中心")
        layout = QVBoxLayout(box)

        self.record_tabs = QTabWidget()
        self.backtest_table = self._new_table(
            ["时间", "代码", "策略", "快线", "慢线", "股数", "总收益", "年化", "回撤", "夏普", "交易数"]
        )
        self.order_table = self._new_table(
            ["时间", "代码", "方向", "价格", "股数", "模式", "成功", "订单号", "状态", "成交号", "结果"]
        )
        self.signal_table = self._new_table(["时间", "代码", "信号", "参考价", "原因"])
        self.broker_order_table = self._new_table(
            ["抓取时间", "订单号", "代码", "方向", "价格", "委托量", "成交量", "状态", "说明"]
        )
        self.trade_table = self._new_table(
            ["抓取时间", "成交号", "订单号", "代码", "方向", "价格", "数量", "成交时间"]
        )
        self.account_snapshot_table = self._new_table(["时间", "来源", "现金", "总资产", "持仓市值"])
        self.position_snapshot_table = self._new_table(
            ["时间", "来源", "代码", "数量", "可用", "成本价", "最新价"]
        )
        self.event_table = self._new_table(["时间", "级别", "类别", "消息"])

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        self.record_tabs.addTab(self.backtest_table, "回测记录")
        self.record_tabs.addTab(self.order_table, "订单记录")
        self.record_tabs.addTab(self.broker_order_table, "委托中心")
        self.record_tabs.addTab(self.trade_table, "成交记录")
        self.record_tabs.addTab(self.signal_table, "信号记录")
        self.record_tabs.addTab(self.account_snapshot_table, "账户快照")
        self.record_tabs.addTab(self.position_snapshot_table, "持仓快照")
        self.record_tabs.addTab(self.event_table, "事件日志")
        self.record_tabs.addTab(self.log_view, "运行日志")
        layout.addWidget(self.record_tabs)
        return box

    def _new_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        return table

    def _choose_config(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(self, "选择配置文件", self.config_path, "TOML Files (*.toml)")
        if chosen:
            self.config_path_edit.setText(chosen)

    def load_config(self) -> None:
        try:
            config_path = Path(self.config_path_edit.text().strip())
            self.config = AppConfig.from_file(config_path) if config_path.exists() else AppConfig()
            self.config_path = str(config_path)
            self.storage = Storage(self._resolve_storage_path(self.config.storage.db_path))

            self.symbol_combo.clear()
            self.symbol_combo.addItems(self.config.data.default_symbols)
            self.fast_window_spin.setValue(self.config.strategy.fast_window)
            self.slow_window_spin.setValue(self.config.strategy.slow_window)
            self.trade_size_spin.setValue(self.config.strategy.trade_size)

            self._refresh_runtime(reset_broker=True)
            self._refresh_status_labels()
            self.sync_broker_state(source="load_config")
            self.refresh_market()
            self.refresh_records()
            self.log(f"加载配置成功: {self.config_path}")
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("加载配置失败", str(exc))

    def _refresh_runtime(self, reset_broker: bool = False) -> None:
        self._apply_strategy_controls_to_config()
        strategy = MovingAverageCrossStrategy(
            fast_window=self.config.strategy.fast_window,
            slow_window=self.config.strategy.slow_window,
        )
        desired_live_mode = self.config.xtquant.enabled and not self.config.risk.dry_run
        if reset_broker or self._broker_mode_mismatch(desired_live_mode):
            if desired_live_mode:
                self.broker = XtQuantBroker(self.config.xtquant)
                self.broker.connect()
            else:
                self.broker = SimulatedBroker()
                self.broker.connect()
        self.live_engine = LiveTradingEngine(strategy, self.data_provider, self.broker, self.config)

    def _broker_mode_mismatch(self, desired_live_mode: bool) -> bool:
        if desired_live_mode:
            return not isinstance(self.broker, XtQuantBroker)
        return not isinstance(self.broker, SimulatedBroker)

    def _apply_strategy_controls_to_config(self) -> None:
        fast_window = self.fast_window_spin.value()
        slow_window = self.slow_window_spin.value()
        if fast_window >= slow_window:
            raise ValueError("快线必须小于慢线")
        self.config.strategy.fast_window = fast_window
        self.config.strategy.slow_window = slow_window
        self.config.strategy.trade_size = self.trade_size_spin.value()

    def _refresh_status_labels(self) -> None:
        mode = "QMT 实盘" if self.config.xtquant.enabled and not self.config.risk.dry_run else "本地 Dry Run"
        self.mode_label.setText(f"模式: {mode}")
        self.strategy_label.setText(
            f"策略: 双均线 {self.config.strategy.fast_window}/{self.config.strategy.slow_window} | "
            f"每次 {self.config.strategy.trade_size} 股"
        )
        self.storage_label.setText(f"数据库: {self.storage.db_path}")

    def run_backtest(self) -> None:
        try:
            self._refresh_runtime()
            self._refresh_status_labels()
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
            self.last_backtest_result = result
            self.price_chart.update_history(history, self.config.strategy.fast_window, self.config.strategy.slow_window)
            self.equity_chart.update_equity_curve(result.equity_curve)
            self.storage.save_backtest(
                BacktestRecord(
                    symbol=symbol,
                    strategy_name=self.config.strategy.name,
                    fast_window=self.config.strategy.fast_window,
                    slow_window=self.config.strategy.slow_window,
                    trade_size=self.config.strategy.trade_size,
                    start_date=self.config.data.start_date,
                    end_date=self.config.data.end_date,
                    result=result,
                )
            )
            self.refresh_records()
            self.log(
                "回测完成 | "
                f"{symbol} | 总收益 {result.total_return:.2%} | 年化 {result.annual_return:.2%} | "
                f"最大回撤 {result.max_drawdown:.2%} | 夏普 {result.sharpe:.2f} | 交易次数 {result.trades}"
            )
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("回测失败", str(exc))

    def evaluate_signal(self) -> None:
        try:
            decision = self._evaluate_current_symbol(save_signal=True)
            self.signal_label.setText(
                f"最近信号: {decision.signal.value.upper()} @ {decision.reference_price:.2f} | {decision.reason}"
            )
            self.log(
                f"信号评估完成 | {decision.symbol} | {decision.signal.value.upper()} | "
                f"{decision.reference_price:.2f} | {decision.reason}"
            )
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("信号评估失败", str(exc))

    def _evaluate_current_symbol(self, save_signal: bool) -> SignalDecision:
        self._refresh_runtime()
        self._refresh_status_labels()
        symbol = self._current_symbol()
        if self.live_engine is None:
            raise RuntimeError("交易引擎尚未初始化")
        decision = self.live_engine.evaluate_symbol(symbol)
        self.last_decision = decision

        history = self.data_provider.get_history(
            symbol=symbol,
            start_date=self.config.data.start_date,
            end_date=self.config.data.end_date,
            adjust=self.config.data.adjust,
        )
        self.price_chart.update_history(history, self.config.strategy.fast_window, self.config.strategy.slow_window)

        if save_signal:
            self.storage.save_signal(decision)
            self.refresh_records()
        return decision

    def execute_signal(self) -> None:
        try:
            symbol = self._current_symbol()
            if self.live_engine is None:
                raise RuntimeError("交易引擎尚未初始化")

            decision = self.last_decision if self.last_decision and self.last_decision.symbol == symbol else None
            if decision is None:
                decision = self._evaluate_current_symbol(save_signal=True)

            request = self.live_engine.build_order_request(decision)
            result = self.live_engine.execute_signal(decision)
            mode = "QMT" if self.config.xtquant.enabled and not self.config.risk.dry_run else "DRY_RUN"
            self.storage.save_order(
                OrderRecord(
                    symbol=decision.symbol,
                    side=decision.signal.value,
                    price=request.price if request else decision.reference_price,
                    volume=request.volume if request else 0,
                    reason=decision.reason,
                    mode=mode,
                    result=result,
                )
            )
            self.signal_label.setText(
                f"最近信号: {decision.signal.value.upper()} @ {decision.reference_price:.2f} | {result.message}"
            )
            self.log(f"执行结果 | {decision.symbol} | {result.message}")
            if result.order_id:
                self.cancel_order_edit.setText(result.order_id)
            self.sync_broker_state(source="execute_signal")
            self.refresh_records()
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("执行失败", str(exc))

    def cancel_order(self) -> None:
        try:
            order_id = self.cancel_order_edit.text().strip()
            if not order_id:
                raise RuntimeError("请先输入要撤销的订单号")
            result = self.broker.cancel_order(order_id)
            self.log(f"撤单结果 | {order_id} | {result.message}")
            self.sync_broker_state(source="cancel_order")
            self.refresh_records()
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("撤单失败", str(exc))

    def refresh_market(self) -> None:
        try:
            symbols = [self.symbol_combo.itemText(i) for i in range(self.symbol_combo.count())]
            if not symbols:
                return
            snapshot = self.data_provider.get_realtime_snapshot(symbols)
            self._populate_frame_table(
                self.quote_table,
                snapshot,
                [
                    ("symbol", lambda value: value),
                    ("name", lambda value: value),
                    ("last_price", lambda value: f"{float(value):.2f}"),
                    ("pct_change", lambda value: f"{float(value):.2f}%"),
                    ("volume", lambda value: str(int(value))),
                    ("updated_at", lambda value: value),
                ],
            )
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

    def sync_broker_state(self, source: str) -> None:
        positions = self.broker.get_positions()
        account = self.broker.get_account()
        orders = self.broker.get_orders()
        trades = self.broker.get_trades()
        events = self.broker.get_events()

        self.storage.save_account_snapshot(AccountSnapshotRecord(account=account, source=source))
        self.storage.save_position_snapshot(positions, source=source)
        self.storage.save_broker_orders(orders)
        self.storage.save_trades(trades)
        self.storage.save_events(events)
        self.refresh_positions()

    def refresh_records(self) -> None:
        self._populate_frame_table(
            self.backtest_table,
            self.storage.list_backtests(),
            [
                ("created_at", str),
                ("symbol", str),
                ("strategy_name", str),
                ("fast_window", lambda value: str(int(value))),
                ("slow_window", lambda value: str(int(value))),
                ("trade_size", lambda value: str(int(value))),
                ("total_return", lambda value: f"{float(value):.2%}"),
                ("annual_return", lambda value: f"{float(value):.2%}"),
                ("max_drawdown", lambda value: f"{float(value):.2%}"),
                ("sharpe", lambda value: f"{float(value):.2f}"),
                ("trades", lambda value: str(int(value))),
            ],
        )
        self._populate_frame_table(
            self.order_table,
            self.storage.list_orders(),
            [
                ("created_at", str),
                ("symbol", str),
                ("side", str),
                ("price", lambda value: f"{float(value):.2f}"),
                ("volume", lambda value: str(int(value))),
                ("mode", str),
                ("accepted", lambda value: "是" if int(value) else "否"),
                ("order_id", lambda value: value or "-"),
                ("status", lambda value: value or "-"),
                ("trade_id", lambda value: value or "-"),
                ("message", str),
            ],
        )
        self._populate_frame_table(
            self.broker_order_table,
            self.storage.list_broker_orders(),
            [
                ("captured_at", str),
                ("order_id", str),
                ("symbol", str),
                ("side", str),
                ("price", lambda value: f"{float(value):.2f}"),
                ("volume", lambda value: str(int(value))),
                ("filled_volume", lambda value: str(int(value))),
                ("status", str),
                ("message", str),
            ],
        )
        self._populate_frame_table(
            self.trade_table,
            self.storage.list_trades(),
            [
                ("captured_at", str),
                ("trade_id", str),
                ("order_id", str),
                ("symbol", str),
                ("side", str),
                ("price", lambda value: f"{float(value):.2f}"),
                ("volume", lambda value: str(int(value))),
                ("created_at", str),
            ],
        )
        self._populate_frame_table(
            self.signal_table,
            self.storage.list_signals(),
            [
                ("created_at", str),
                ("symbol", str),
                ("signal", str),
                ("reference_price", lambda value: f"{float(value):.2f}"),
                ("reason", str),
            ],
        )
        self._populate_frame_table(
            self.account_snapshot_table,
            self.storage.list_account_snapshots(),
            [
                ("created_at", str),
                ("source", str),
                ("cash", lambda value: f"{float(value):,.2f}"),
                ("equity", lambda value: f"{float(value):,.2f}"),
                ("market_value", lambda value: f"{float(value):,.2f}"),
            ],
        )
        self._populate_frame_table(
            self.position_snapshot_table,
            self.storage.list_position_snapshots(),
            [
                ("created_at", str),
                ("source", str),
                ("symbol", str),
                ("volume", lambda value: str(int(value))),
                ("available_volume", lambda value: str(int(value))),
                ("avg_price", lambda value: f"{float(value):.2f}"),
                ("last_price", lambda value: f"{float(value):.2f}"),
            ],
        )
        self._populate_frame_table(
            self.event_table,
            self.storage.list_events(),
            [
                ("created_at", str),
                ("level", str),
                ("category", str),
                ("message", str),
            ],
        )

    def _populate_frame_table(self, table: QTableWidget, frame, columns) -> None:
        table.setRowCount(0 if frame is None else len(frame))
        if frame is None or getattr(frame, "empty", True):
            return
        for row_idx, (_, row) in enumerate(frame.iterrows()):
            for col_idx, (column_name, formatter) in enumerate(columns):
                raw_value = row.get(column_name, "")
                value = formatter(raw_value) if raw_value != "" else ""
                table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))

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

    def _resolve_storage_path(self, db_path: str) -> Path:
        path = Path(db_path)
        if path.is_absolute():
            return path
        return Path.cwd() / path

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
