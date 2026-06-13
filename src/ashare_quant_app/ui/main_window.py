from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
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
        self.resize(1600, 1020)

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
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._handle_auto_refresh)

        self._apply_theme()
        self._build_ui()
        self.config_path_edit.setText(self.config_path)
        self.load_config()

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #0b1220;
                color: #dbe4f0;
                font-size: 13px;
            }
            QFrame#Card {
                background: #111a2e;
                border: 1px solid #1d2942;
                border-radius: 14px;
            }
            QFrame#StatusCard {
                background: #13203a;
                border: 1px solid #223252;
                border-radius: 12px;
            }
            QLabel#SectionTitle {
                font-size: 15px;
                font-weight: 700;
                color: #f3f7fb;
            }
            QLabel#SectionHint {
                color: #8ea2c0;
                font-size: 12px;
            }
            QLabel#StatusValue {
                font-size: 13px;
                font-weight: 600;
                color: #ffffff;
            }
            QLabel#StatusCaption {
                color: #87a0c0;
                font-size: 11px;
            }
            QGroupBox {
                border: 1px solid #1d2942;
                border-radius: 12px;
                margin-top: 14px;
                padding-top: 10px;
                background: #111a2e;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #cfe0f5;
            }
            QPushButton {
                background: #1d4ed8;
                border: 1px solid #2d63ee;
                border-radius: 8px;
                padding: 8px 14px;
                color: white;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2b5fe7;
            }
            QPushButton:pressed {
                background: #1845c0;
            }
            QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {
                background: #0d1729;
                border: 1px solid #233452;
                border-radius: 8px;
                padding: 6px 8px;
                color: #e9f0f8;
            }
            QTableWidget, QTabWidget::pane {
                background: #0d1729;
                border: 1px solid #233452;
                border-radius: 10px;
                gridline-color: #1b2942;
            }
            QHeaderView::section {
                background: #13203a;
                color: #bcd0ea;
                border: none;
                border-bottom: 1px solid #233452;
                padding: 8px;
                font-weight: 600;
            }
            QTableWidget {
                selection-background-color: #1f4fd1;
                selection-color: white;
            }
            QTabBar::tab {
                background: #111a2e;
                color: #9eb2cf;
                padding: 8px 14px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #1b2a47;
                color: #ffffff;
            }
            QCheckBox {
                spacing: 6px;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            """
        )

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(self._build_header_panel())
        layout.addWidget(self._build_status_panel())
        layout.addWidget(self._build_workspace(), 1)
        layout.addWidget(self._build_records_panel(), 1)

        self.setCentralWidget(root)

    def _build_header_panel(self) -> QFrame:
        card = self._make_card("StatusCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)

        title_layout = QVBoxLayout()
        title = QLabel("A股量化交易工作台")
        title.setObjectName("SectionTitle")
        hint = QLabel("参考主流量化终端布局，聚合策略、行情、风控、图表和交易记录")
        hint.setObjectName("SectionHint")
        title_layout.addWidget(title)
        title_layout.addWidget(hint)

        layout.addLayout(title_layout, 1)
        layout.addWidget(self._make_status_badge("运行模式", "本地模拟 / QMT"), 0)
        layout.addWidget(self._make_status_badge("数据链路", "实时 / 回退"), 0)
        return card

    def _build_control_panel(self) -> QFrame:
        card = self._make_card()
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        outer.addWidget(self._make_section_header("策略与风控", "调整参数后可直接刷新运行时配置"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

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
        self.stop_loss_spin = QSpinBox()
        self.stop_loss_spin.setRange(0, 50)
        self.take_profit_spin = QSpinBox()
        self.take_profit_spin.setRange(0, 200)
        self.max_trades_spin = QSpinBox()
        self.max_trades_spin.setRange(1, 999)
        self.min_interval_spin = QSpinBox()
        self.min_interval_spin.setRange(0, 3600)
        self.auto_refresh_check = QCheckBox("自动刷新")
        self.auto_execute_check = QCheckBox("自动执行")
        self.auto_refresh_interval_spin = QSpinBox()
        self.auto_refresh_interval_spin.setRange(5, 3600)
        self.auto_refresh_check.stateChanged.connect(self._on_auto_refresh_settings_changed)
        self.auto_execute_check.stateChanged.connect(self._on_auto_refresh_settings_changed)
        self.auto_refresh_interval_spin.valueChanged.connect(self._on_auto_refresh_settings_changed)

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
        grid.addWidget(self.config_path_edit, 0, 1, 1, 3)
        grid.addWidget(browse_btn, 0, 4)
        grid.addWidget(load_btn, 0, 5)

        grid.addWidget(QLabel("交易标的"), 1, 0)
        grid.addWidget(self.symbol_combo, 1, 1)
        grid.addWidget(QLabel("快线"), 1, 2)
        grid.addWidget(self.fast_window_spin, 1, 3)
        grid.addWidget(QLabel("慢线"), 1, 4)
        grid.addWidget(self.slow_window_spin, 1, 5)
        grid.addWidget(QLabel("每次股数"), 2, 0)
        grid.addWidget(self.trade_size_spin, 2, 1)

        grid.addWidget(QLabel("止损%"), 2, 2)
        grid.addWidget(self.stop_loss_spin, 2, 3)
        grid.addWidget(QLabel("止盈%"), 2, 4)
        grid.addWidget(self.take_profit_spin, 2, 5)
        grid.addWidget(QLabel("日内上限"), 3, 0)
        grid.addWidget(self.max_trades_spin, 3, 1)
        grid.addWidget(QLabel("最小间隔秒"), 3, 2)
        grid.addWidget(self.min_interval_spin, 3, 3)

        grid.addWidget(self.auto_refresh_check, 4, 0)
        grid.addWidget(self.auto_execute_check, 4, 1)
        grid.addWidget(QLabel("刷新秒数"), 4, 2)
        grid.addWidget(self.auto_refresh_interval_spin, 4, 3)
        grid.addWidget(QLabel("撤单订单号"), 4, 4)
        grid.addWidget(self.cancel_order_edit, 4, 5)
        grid.addWidget(cancel_btn, 4, 6)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addWidget(backtest_btn)
        action_row.addWidget(signal_btn)
        action_row.addWidget(execute_btn)
        action_row.addWidget(quote_btn)
        action_row.addWidget(position_btn)
        action_row.addWidget(refresh_record_btn)
        action_row.addStretch(1)

        outer.addLayout(grid)
        outer.addLayout(action_row)
        return card

    def _build_status_panel(self) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        self.mode_label = QLabel("-")
        self.strategy_label = QLabel("-")
        self.storage_label = QLabel("-")
        self.account_label = QLabel("-")
        self.signal_label = QLabel("-")
        self.refresh_label = QLabel("手动")

        row.addWidget(self._make_info_card("运行模式", self.mode_label))
        row.addWidget(self._make_info_card("当前策略", self.strategy_label))
        row.addWidget(self._make_info_card("账户资产", self.account_label))
        row.addWidget(self._make_info_card("最近信号", self.signal_label))
        row.addWidget(self._make_info_card("刷新状态", self.refresh_label))
        row.addWidget(self._make_info_card("数据库", self.storage_label))
        return container

    def _build_workspace(self) -> QWidget:
        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)

        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sidebar_scroll.setWidget(self._build_control_panel())

        center_card = self._make_card()
        center_layout = QVBoxLayout(center_card)
        center_layout.setContentsMargins(16, 16, 16, 16)
        center_layout.setSpacing(10)
        center_layout.addWidget(self._make_section_header("图表分析", "查看价格结构、均线形态和权益曲线"))
        self.price_chart = PriceChartView()
        self.equity_chart = EquityChartView()
        center_layout.addWidget(self.price_chart, 1)
        center_layout.addWidget(self.equity_chart, 1)

        right_card = self._make_card()
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)
        right_layout.addWidget(self._make_section_header("市场监控", "实时行情、持仓与交易监视"))
        right_layout.addWidget(QLabel("实时行情"))
        self.quote_table = self._new_table(["代码", "名称", "最新价", "涨跌幅", "成交量", "更新时间", "来源"])
        right_layout.addWidget(self.quote_table, 3)
        right_layout.addWidget(QLabel("当前持仓"))
        self.position_table = self._new_table(["代码", "数量", "可用", "成本价", "最新价"])
        right_layout.addWidget(self.position_table, 2)

        splitter.addWidget(sidebar_scroll)
        splitter.addWidget(center_card)
        splitter.addWidget(right_card)
        splitter.setSizes([420, 700, 480])
        return splitter

    def _build_records_panel(self) -> QFrame:
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self._make_section_header("交易记录中心", "集中查看回测、委托、成交、快照与事件"))

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
        return card

    def _new_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        return table

    def _make_card(self, object_name: str = "Card") -> QFrame:
        frame = QFrame()
        frame.setObjectName(object_name)
        return frame

    def _make_section_header(self, title: str, hint: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        hint_label = QLabel(hint)
        hint_label.setObjectName("SectionHint")
        layout.addWidget(title_label)
        layout.addWidget(hint_label)
        return widget

    def _make_info_card(self, caption: str, value_label: QLabel) -> QFrame:
        frame = self._make_card("StatusCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        caption_label = QLabel(caption)
        caption_label.setObjectName("StatusCaption")
        value_label.setObjectName("StatusValue")
        value_label.setWordWrap(True)
        layout.addWidget(caption_label)
        layout.addWidget(value_label)
        return frame

    def _make_status_badge(self, caption: str, value: str) -> QFrame:
        label = QLabel(value)
        return self._make_info_card(caption, label)

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
            self.stop_loss_spin.setValue(int(self.config.risk.stop_loss_pct * 100))
            self.take_profit_spin.setValue(int(self.config.risk.take_profit_pct * 100))
            self.max_trades_spin.setValue(self.config.risk.max_daily_trades)
            self.min_interval_spin.setValue(self.config.risk.min_trade_interval_seconds)
            self.auto_refresh_check.setChecked(self.config.auto_refresh.enabled)
            self.auto_execute_check.setChecked(self.config.auto_refresh.auto_execute_signals)
            self.auto_refresh_interval_spin.setValue(self.config.auto_refresh.interval_seconds)

            self._refresh_runtime(reset_broker=True)
            self._refresh_status_labels()
            self.sync_broker_state(source="load_config")
            self.refresh_market()
            self.refresh_records()
            self._configure_auto_refresh()
            self.log(f"加载配置成功: {self.config_path}")
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("加载配置失败", str(exc))

    def _refresh_runtime(self, reset_broker: bool = False) -> None:
        self._apply_strategy_controls_to_config()
        self.data_provider = AkshareDataProvider(realtime_provider=self.config.data.realtime_provider)
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
        self.config.risk.stop_loss_pct = self.stop_loss_spin.value() / 100
        self.config.risk.take_profit_pct = self.take_profit_spin.value() / 100
        self.config.risk.max_daily_trades = self.max_trades_spin.value()
        self.config.risk.min_trade_interval_seconds = self.min_interval_spin.value()
        self.config.auto_refresh.enabled = self.auto_refresh_check.isChecked()
        self.config.auto_refresh.auto_execute_signals = self.auto_execute_check.isChecked()
        self.config.auto_refresh.interval_seconds = self.auto_refresh_interval_spin.value()

    def _refresh_status_labels(self) -> None:
        mode = "QMT 实盘" if self.config.xtquant.enabled and not self.config.risk.dry_run else "本地 Dry Run"
        self.mode_label.setText(f"模式: {mode}")
        self.strategy_label.setText(
            f"策略: 双均线 {self.config.strategy.fast_window}/{self.config.strategy.slow_window} | "
            f"每次 {self.config.strategy.trade_size} 股"
        )
        self.storage_label.setText(f"数据库: {self.storage.db_path}")
        refresh_text = (
            f"刷新: 每 {self.config.auto_refresh.interval_seconds}s"
            if self.config.auto_refresh.enabled
            else "刷新: 手动"
        )
        self.refresh_label.setText(refresh_text)

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
            price_map = {
                str(row["symbol"]): float(row["last_price"])
                for _, row in snapshot.iterrows()
                if "symbol" in row and "last_price" in row
            }
            self.broker.update_market_prices(price_map)
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
                    ("data_source", lambda value: value),
                ],
            )
            source = snapshot.iloc[0]["data_source"] if not snapshot.empty and "data_source" in snapshot.columns else "unknown"
            self.log(f"刷新行情成功，共 {len(snapshot)} 条，来源 {source}")
            self.refresh_positions()
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

    def _configure_auto_refresh(self) -> None:
        if self.config.auto_refresh.enabled:
            self.refresh_timer.start(self.config.auto_refresh.interval_seconds * 1000)
        else:
            self.refresh_timer.stop()

    def _on_auto_refresh_settings_changed(self) -> None:
        self.config.auto_refresh.enabled = self.auto_refresh_check.isChecked()
        self.config.auto_refresh.auto_execute_signals = self.auto_execute_check.isChecked()
        self.config.auto_refresh.interval_seconds = self.auto_refresh_interval_spin.value()
        self._refresh_status_labels()
        self._configure_auto_refresh()

    def _handle_auto_refresh(self) -> None:
        try:
            self._refresh_runtime()
            self._refresh_status_labels()
            self.refresh_market()
            if self.config.auto_refresh.sync_broker_state:
                self.sync_broker_state(source="auto_refresh")
            self.refresh_records()
            if self.config.auto_refresh.auto_execute_signals:
                symbol = self._current_symbol()
                decision = self._evaluate_current_symbol(save_signal=True)
                if decision.symbol == symbol and decision.signal.value != "hold":
                    self.execute_signal()
        except Exception as exc:  # pragma: no cover - UI path
            self.log(f"自动刷新异常: {exc}")

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
