from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
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
        self.setWindowTitle("A鑲￠噺鍖栦氦鏄撶粓绔?)
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
        self.last_data_source = "unknown"
        self.last_refresh_at = "-"
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
                background: #f5f7fb;
                color: #1f2937;
                font-size: 13px;
            }
            QFrame#Card {
                background: #ffffff;
                border: 1px solid #dde5f0;
                border-radius: 14px;
            }
            QFrame#StatusCard {
                background: #ffffff;
                border: 1px solid #d8e1ee;
                border-radius: 12px;
            }
            QLabel#SectionTitle {
                font-size: 15px;
                font-weight: 700;
                color: #0f172a;
            }
            QLabel#SectionHint {
                color: #64748b;
                font-size: 12px;
            }
            QLabel#StatusValue {
                font-size: 13px;
                font-weight: 600;
                color: #0f172a;
            }
            QLabel#StatusCaption {
                color: #64748b;
                font-size: 11px;
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
                background: #ffffff;
                border: 1px solid #cfd8e3;
                border-radius: 8px;
                padding: 6px 8px;
                color: #111827;
            }
            QTableWidget, QTabWidget::pane {
                background: #ffffff;
                border: 1px solid #d6deea;
                border-radius: 10px;
                gridline-color: #e8edf5;
            }
            QHeaderView::section {
                background: #f8fafc;
                color: #334155;
                border: none;
                border-bottom: 1px solid #d6deea;
                padding: 8px;
                font-weight: 600;
            }
            QTableWidget {
                selection-background-color: #1f4fd1;
                selection-color: white;
                alternate-background-color: #f8fbff;
            }
            QTabBar::tab {
                background: #eef3f9;
                color: #64748b;
                padding: 8px 14px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border: 1px solid #d6deea;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f172a;
            }
            QCheckBox {
                spacing: 6px;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QMenuBar {
                background: #ffffff;
                border-bottom: 1px solid #d6deea;
                padding: 4px 6px;
            }
            QMenuBar::item {
                background: transparent;
                color: #334155;
                padding: 6px 10px;
                border-radius: 6px;
            }
            QMenuBar::item:selected {
                background: #eef4ff;
                color: #1d4ed8;
            }
            QMenu {
                background: #ffffff;
                border: 1px solid #d6deea;
                padding: 6px;
            }
            QMenu::item {
                padding: 7px 22px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background: #eef4ff;
                color: #1d4ed8;
            }
            QStatusBar {
                background: #ffffff;
                border-top: 1px solid #d6deea;
                color: #475569;
                font-size: 11px;
            }
            """
        )

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(self._build_header_panel())
        layout.addWidget(self._build_workspace(), 1)
        layout.addWidget(self._build_records_panel(), 1)

        self.setCentralWidget(root)
        self._build_menu_bar()
        self._build_bottom_status_bar()

    def _build_header_panel(self) -> QFrame:
        card = self._make_card("StatusCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)

        title_layout = QVBoxLayout()
        title = QLabel("A鑲￠噺鍖栦氦鏄撳伐浣滃彴")
        title.setObjectName("SectionTitle")
        hint = QLabel("鍙傝€冧富娴侀噺鍖栫粓绔竷灞€锛岃仛鍚堢瓥鐣ャ€佽鎯呫€侀鎺с€佸浘琛ㄥ拰浜ゆ槗璁板綍")
        hint.setObjectName("SectionHint")
        title_layout.addWidget(title)
        title_layout.addWidget(hint)

        layout.addLayout(title_layout, 1)
        return card

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.clear()

        strategy_menu = menu_bar.addMenu("绛栫暐椋庢帶閰嶇疆")
        self.strategy_panel_action = QAction("鏄剧ず鍙傛暟闈㈡澘", self)
        self.strategy_panel_action.setCheckable(True)
        self.strategy_panel_action.setChecked(True)
        self.strategy_panel_action.toggled.connect(
            lambda checked: self._set_panel_visible(self.control_panel_container, checked)
        )
        strategy_menu.addAction(self.strategy_panel_action)

        self.auto_refresh_action = QAction("鍚敤鑷姩鍒锋柊", self)
        self.auto_refresh_action.setCheckable(True)
        self.auto_refresh_action.setChecked(self.auto_refresh_check.isChecked())
        self.auto_refresh_action.toggled.connect(self.auto_refresh_check.setChecked)
        strategy_menu.addAction(self.auto_refresh_action)

        load_config_action = QAction("閲嶆柊鍔犺浇閰嶇疆", self)
        load_config_action.triggered.connect(self.load_config)
        strategy_menu.addAction(load_config_action)

        focus_strategy_action = QAction("鑱氱劍鍙傛暟闈㈡澘", self)
        focus_strategy_action.triggered.connect(lambda: self._focus_panel(self.control_panel_container))
        strategy_menu.addAction(focus_strategy_action)

        market_menu = menu_bar.addMenu("甯傚満鐩戞帶")
        self.market_panel_action = QAction("鏄剧ず甯傚満鐩戞帶", self)
        self.market_panel_action.setCheckable(True)
        self.market_panel_action.setChecked(True)
        self.market_panel_action.toggled.connect(lambda checked: self._set_panel_visible(self.market_panel_card, checked))
        market_menu.addAction(self.market_panel_action)

        refresh_market_action = QAction("鍒锋柊琛屾儏", self)
        refresh_market_action.triggered.connect(self.refresh_market)
        market_menu.addAction(refresh_market_action)

        refresh_positions_action = QAction("鍒锋柊鎸佷粨", self)
        refresh_positions_action.triggered.connect(self.refresh_positions)
        market_menu.addAction(refresh_positions_action)

        focus_market_action = QAction("鑱氱劍甯傚満鐩戞帶", self)
        focus_market_action.triggered.connect(lambda: self._focus_panel(self.market_panel_card))
        market_menu.addAction(focus_market_action)

        records_menu = menu_bar.addMenu("浜ゆ槗璁板綍")
        self.records_panel_action = QAction("鏄剧ず浜ゆ槗璁板綍闈㈡澘", self)
        self.records_panel_action.setCheckable(True)
        self.records_panel_action.setChecked(True)
        self.records_panel_action.toggled.connect(
            lambda checked: self._set_panel_visible(self.records_panel_card, checked)
        )
        records_menu.addAction(self.records_panel_action)

        focus_records_action = QAction("鑱氱劍浜ゆ槗璁板綍", self)
        focus_records_action.triggered.connect(lambda: self._focus_panel(self.records_panel_card))
        records_menu.addAction(focus_records_action)

        order_records_action = QAction("鍒囨崲鍒板鎵樹腑蹇?, self)
        order_records_action.triggered.connect(lambda: self._open_record_tab("濮旀墭涓績"))
        records_menu.addAction(order_records_action)

        trade_records_action = QAction("鍒囨崲鍒版垚浜よ褰?, self)
        trade_records_action.triggered.connect(lambda: self._open_record_tab("鎴愪氦璁板綍"))
        records_menu.addAction(trade_records_action)

        event_records_action = QAction("鍒囨崲鍒颁簨浠舵棩蹇?, self)
        event_records_action.triggered.connect(lambda: self._open_record_tab("浜嬩欢鏃ュ織"))
        records_menu.addAction(event_records_action)

        chart_menu = menu_bar.addMenu("鍥捐〃鍒嗘瀽")
        self.chart_panel_action = QAction("鏄剧ず鍥捐〃鍒嗘瀽", self)
        self.chart_panel_action.setCheckable(True)
        self.chart_panel_action.setChecked(True)
        self.chart_panel_action.toggled.connect(lambda checked: self._set_panel_visible(self.chart_panel_card, checked))
        chart_menu.addAction(self.chart_panel_action)

        run_backtest_action = QAction("杩愯鍥炴祴", self)
        run_backtest_action.triggered.connect(self.run_backtest)
        chart_menu.addAction(run_backtest_action)

        evaluate_signal_action = QAction("璇勪及褰撳墠淇″彿", self)
        evaluate_signal_action.triggered.connect(self.evaluate_signal)
        chart_menu.addAction(evaluate_signal_action)

        focus_chart_action = QAction("鑱氱劍鍥捐〃鍒嗘瀽", self)
        focus_chart_action.triggered.connect(lambda: self._focus_panel(self.chart_panel_card))
        chart_menu.addAction(focus_chart_action)

    def _build_bottom_status_bar(self) -> None:
        status_bar = self.statusBar()
        status_bar.setSizeGripEnabled(False)
        self.mode_label = self._new_status_label(150)
        self.strategy_label = self._new_status_label(260)
        self.account_label = self._new_status_label(320)
        self.signal_label = self._new_status_label(300)
        self.refresh_label = self._new_status_label(170)
        self.data_source_label = self._new_status_label(150)
        self.storage_label = self._new_status_label(260)

        for label in [
            self.mode_label,
            self.strategy_label,
            self.account_label,
            self.signal_label,
            self.refresh_label,
            self.data_source_label,
            self.storage_label,
        ]:
            status_bar.addWidget(label)

        self.mode_label.setText("妯″紡: -")
        self.strategy_label.setText("绛栫暐: -")
        self.account_label.setText("璐︽埛: -")
        self.signal_label.setText("鏈€杩戜俊鍙? -")
        self.refresh_label.setText("鍒锋柊: -")
        self.data_source_label.setText("鏁版嵁閾捐矾: -")
        self.storage_label.setText("鏁版嵁搴? -")

    def _new_status_label(self, minimum_width: int) -> QLabel:
        label = QLabel()
        label.setMinimumWidth(minimum_width)
        label.setMargin(6)
        label.setStyleSheet("padding: 0 6px;")
        return label

    def _sync_panel_action(self, widget: QWidget, visible: bool) -> None:
        action_map = {
            self.control_panel_container: self.strategy_panel_action,
            self.chart_panel_card: self.chart_panel_action,
            self.market_panel_card: self.market_panel_action,
            self.records_panel_card: self.records_panel_action,
        }
        action = action_map.get(widget)
        if action is not None and action.isChecked() != visible:
            action.blockSignals(True)
            action.setChecked(visible)
            action.blockSignals(False)

    def _set_panel_visible(self, widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)
        self._sync_panel_action(widget, visible)
        if visible:
            self._focus_panel(widget)

    def _focus_panel(self, widget: QWidget) -> None:
        self._sync_panel_action(widget, True)
        widget.show()
        if widget is self.control_panel_container:
            self.control_panel_container.ensureWidgetVisible(self.control_panel_card)
        if hasattr(self, "workspace_splitter"):
            self.workspace_splitter.setSizes([420, 700, 480])
        widget.setFocus(Qt.FocusReason.OtherFocusReason)

    def _open_record_tab(self, tab_name: str) -> None:
        self._sync_panel_action(self.records_panel_card, True)
        self.records_panel_card.show()
        index = next(
            (
                idx
                for idx in range(self.record_tabs.count())
                if self.record_tabs.tabText(idx) == tab_name
            ),
            -1,
        )
        if index >= 0:
            self.record_tabs.setCurrentIndex(index)
        self._focus_panel(self.records_panel_card)

    def _build_control_panel(self) -> QFrame:
        card = self._make_card()
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        outer.addWidget(self._make_section_header("绛栫暐涓庨鎺?, "璋冩暣鍙傛暟鍚庡彲鐩存帴鍒锋柊杩愯鏃堕厤缃?))

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        self.config_path_edit = QLineEdit()
        browse_btn = QPushButton("閫夋嫨閰嶇疆")
        load_btn = QPushButton("鍔犺浇閰嶇疆")
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
        self.auto_refresh_check = QCheckBox("鑷姩鍒锋柊")
        self.auto_execute_check = QCheckBox("鑷姩鎵ц")
        self.auto_refresh_interval_spin = QSpinBox()
        self.auto_refresh_interval_spin.setRange(5, 3600)
        self.auto_refresh_check.stateChanged.connect(self._on_auto_refresh_settings_changed)
        self.auto_execute_check.stateChanged.connect(self._on_auto_refresh_settings_changed)
        self.auto_refresh_interval_spin.valueChanged.connect(self._on_auto_refresh_settings_changed)

        backtest_btn = QPushButton("杩愯鍥炴祴")
        signal_btn = QPushButton("璇勪及淇″彿")
        execute_btn = QPushButton("鎵ц淇″彿")
        cancel_btn = QPushButton("鎾ら攢濮旀墭")
        quote_btn = QPushButton("鍒锋柊琛屾儏")
        position_btn = QPushButton("鍒锋柊鎸佷粨")
        refresh_record_btn = QPushButton("鍒锋柊璁板綍")

        backtest_btn.clicked.connect(self.run_backtest)
        signal_btn.clicked.connect(self.evaluate_signal)
        execute_btn.clicked.connect(self.execute_signal)
        cancel_btn.clicked.connect(self.cancel_order)
        quote_btn.clicked.connect(self.refresh_market)
        position_btn.clicked.connect(self.refresh_positions)
        refresh_record_btn.clicked.connect(self.refresh_records)

        grid.addWidget(QLabel("閰嶇疆鏂囦欢"), 0, 0)
        grid.addWidget(self.config_path_edit, 0, 1, 1, 3)
        grid.addWidget(browse_btn, 0, 4)
        grid.addWidget(load_btn, 0, 5)

        grid.addWidget(QLabel("浜ゆ槗鏍囩殑"), 1, 0)
        grid.addWidget(self.symbol_combo, 1, 1)
        grid.addWidget(QLabel("蹇嚎"), 1, 2)
        grid.addWidget(self.fast_window_spin, 1, 3)
        grid.addWidget(QLabel("鎱㈢嚎"), 1, 4)
        grid.addWidget(self.slow_window_spin, 1, 5)
        grid.addWidget(QLabel("姣忔鑲℃暟"), 2, 0)
        grid.addWidget(self.trade_size_spin, 2, 1)

        grid.addWidget(QLabel("姝㈡崯%"), 2, 2)
        grid.addWidget(self.stop_loss_spin, 2, 3)
        grid.addWidget(QLabel("姝㈢泩%"), 2, 4)
        grid.addWidget(self.take_profit_spin, 2, 5)
        grid.addWidget(QLabel("鏃ュ唴涓婇檺"), 3, 0)
        grid.addWidget(self.max_trades_spin, 3, 1)
        grid.addWidget(QLabel("鏈€灏忛棿闅旂"), 3, 2)
        grid.addWidget(self.min_interval_spin, 3, 3)

        grid.addWidget(self.auto_refresh_check, 4, 0)
        grid.addWidget(self.auto_execute_check, 4, 1)
        grid.addWidget(QLabel("鍒锋柊绉掓暟"), 4, 2)
        grid.addWidget(self.auto_refresh_interval_spin, 4, 3)
        grid.addWidget(QLabel("鎾ゅ崟璁㈠崟鍙?), 4, 4)
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

    def _build_workspace(self) -> QWidget:
        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        self.workspace_splitter = splitter

        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.control_panel_card = self._build_control_panel()
        sidebar_scroll.setWidget(self.control_panel_card)
        self.control_panel_container = sidebar_scroll

        center_card = self._make_card()
        self.chart_panel_card = center_card
        center_layout = QVBoxLayout(center_card)
        center_layout.setContentsMargins(16, 16, 16, 16)
        center_layout.setSpacing(10)
        center_layout.addWidget(self._make_section_header("鍥捐〃鍒嗘瀽", "鏌ョ湅浠锋牸缁撴瀯銆佸潎绾垮舰鎬佸拰鏉冪泭鏇茬嚎"))
        self.price_chart = PriceChartView()
        self.equity_chart = EquityChartView()
        center_layout.addWidget(self.price_chart, 1)
        center_layout.addWidget(self.equity_chart, 1)

        right_card = self._make_card()
        self.market_panel_card = right_card
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)
        right_layout.addWidget(self._make_section_header("甯傚満鐩戞帶", "瀹炴椂琛屾儏銆佹寔浠撲笌浜ゆ槗鐩戣"))
        right_layout.addWidget(QLabel("瀹炴椂琛屾儏"))
        self.quote_table = self._new_table(["浠ｇ爜", "鍚嶇О", "鏈€鏂颁环", "娑ㄨ穼骞?, "鎴愪氦閲?, "鏇存柊鏃堕棿", "鏉ユ簮"])
        right_layout.addWidget(self.quote_table, 3)
        right_layout.addWidget(QLabel("褰撳墠鎸佷粨"))
        self.position_table = self._new_table(["浠ｇ爜", "鏁伴噺", "鍙敤", "鎴愭湰浠?, "鏈€鏂颁环"])
        right_layout.addWidget(self.position_table, 2)

        splitter.addWidget(sidebar_scroll)
        splitter.addWidget(center_card)
        splitter.addWidget(right_card)
        splitter.setSizes([420, 700, 480])
        return splitter

    def _build_records_panel(self) -> QFrame:
        card = self._make_card()
        self.records_panel_card = card
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self._make_section_header("浜ゆ槗璁板綍涓績", "闆嗕腑鏌ョ湅鍥炴祴銆佸鎵樸€佹垚浜ゃ€佸揩鐓т笌浜嬩欢"))

        self.record_tabs = QTabWidget()
        self.backtest_table = self._new_table(
            ["鏃堕棿", "浠ｇ爜", "绛栫暐", "蹇嚎", "鎱㈢嚎", "鑲℃暟", "鎬绘敹鐩?, "骞村寲", "鍥炴挙", "澶忔櫘", "浜ゆ槗鏁?]
        )
        self.order_table = self._new_table(
            ["鏃堕棿", "浠ｇ爜", "鏂瑰悜", "浠锋牸", "鑲℃暟", "妯″紡", "鎴愬姛", "璁㈠崟鍙?, "鐘舵€?, "鎴愪氦鍙?, "缁撴灉"]
        )
        self.signal_table = self._new_table(["鏃堕棿", "浠ｇ爜", "淇″彿", "鍙傝€冧环", "鍘熷洜"])
        self.broker_order_table = self._new_table(
            ["鎶撳彇鏃堕棿", "璁㈠崟鍙?, "浠ｇ爜", "鏂瑰悜", "浠锋牸", "濮旀墭閲?, "鎴愪氦閲?, "鐘舵€?, "璇存槑"]
        )
        self.trade_table = self._new_table(
            ["鎶撳彇鏃堕棿", "鎴愪氦鍙?, "璁㈠崟鍙?, "浠ｇ爜", "鏂瑰悜", "浠锋牸", "鏁伴噺", "鎴愪氦鏃堕棿"]
        )
        self.account_snapshot_table = self._new_table(["鏃堕棿", "鏉ユ簮", "鐜伴噾", "鎬昏祫浜?, "鎸佷粨甯傚€?])
        self.position_snapshot_table = self._new_table(
            ["鏃堕棿", "鏉ユ簮", "浠ｇ爜", "鏁伴噺", "鍙敤", "鎴愭湰浠?, "鏈€鏂颁环"]
        )
        self.event_table = self._new_table(["鏃堕棿", "绾у埆", "绫诲埆", "娑堟伅"])

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        self.record_tabs.addTab(self.backtest_table, "鍥炴祴璁板綍")
        self.record_tabs.addTab(self.order_table, "璁㈠崟璁板綍")
        self.record_tabs.addTab(self.broker_order_table, "濮旀墭涓績")
        self.record_tabs.addTab(self.trade_table, "鎴愪氦璁板綍")
        self.record_tabs.addTab(self.signal_table, "淇″彿璁板綍")
        self.record_tabs.addTab(self.account_snapshot_table, "璐︽埛蹇収")
        self.record_tabs.addTab(self.position_snapshot_table, "鎸佷粨蹇収")
        self.record_tabs.addTab(self.event_table, "浜嬩欢鏃ュ織")
        self.record_tabs.addTab(self.log_view, "杩愯鏃ュ織")
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
        chosen, _ = QFileDialog.getOpenFileName(self, "閫夋嫨閰嶇疆鏂囦欢", self.config_path, "TOML Files (*.toml)")
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
            self.log(f"鍔犺浇閰嶇疆鎴愬姛: {self.config_path}")
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("鍔犺浇閰嶇疆澶辫触", str(exc))

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
            raise ValueError("蹇嚎蹇呴』灏忎簬鎱㈢嚎")
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
        mode = "QMT 瀹炵洏" if self.config.xtquant.enabled and not self.config.risk.dry_run else "鏈湴 Dry Run"
        self.mode_label.setText(f"妯″紡: {mode}")
        self.strategy_label.setText(
            f"绛栫暐: 鍙屽潎绾?{self.config.strategy.fast_window}/{self.config.strategy.slow_window} | "
            f"姣忔 {self.config.strategy.trade_size} 鑲?
        )
        self.storage_label.setText(f"鏁版嵁搴? {self.storage.db_path}")
        refresh_mode = f"姣?{self.config.auto_refresh.interval_seconds}s" if self.config.auto_refresh.enabled else "鎵嬪姩"
        refresh_text = f"鍒锋柊: {refresh_mode} | 鏈€杩?{self.last_refresh_at}"
        self.refresh_label.setText(refresh_text)
        self.data_source_label.setText(f"鏁版嵁閾捐矾: {self.last_data_source}")
        if hasattr(self, "auto_refresh_action") and self.auto_refresh_action.isChecked() != self.auto_refresh_check.isChecked():
            self.auto_refresh_action.setChecked(self.auto_refresh_check.isChecked())
        try:
            account = self.broker.get_account()
            self.account_label.setText(
                f"璐︽埛: 鐜伴噾 {account.cash:,.0f} | 鎬昏祫浜?{account.equity:,.0f}"
            )
        except Exception:
            self.account_label.setText("璐︽埛: -")

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
                "鍥炴祴瀹屾垚 | "
                f"{symbol} | 鎬绘敹鐩?{result.total_return:.2%} | 骞村寲 {result.annual_return:.2%} | "
                f"鏈€澶у洖鎾?{result.max_drawdown:.2%} | 澶忔櫘 {result.sharpe:.2f} | 浜ゆ槗娆℃暟 {result.trades}"
            )
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("鍥炴祴澶辫触", str(exc))

    def evaluate_signal(self) -> None:
        try:
            decision = self._evaluate_current_symbol(save_signal=True)
            self.signal_label.setText(
                f"鏈€杩戜俊鍙? {decision.signal.value.upper()} @ {decision.reference_price:.2f} | {decision.reason}"
            )
            self.log(
                f"淇″彿璇勪及瀹屾垚 | {decision.symbol} | {decision.signal.value.upper()} | "
                f"{decision.reference_price:.2f} | {decision.reason}"
            )
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("淇″彿璇勪及澶辫触", str(exc))

    def _evaluate_current_symbol(self, save_signal: bool) -> SignalDecision:
        self._refresh_runtime()
        self._refresh_status_labels()
        symbol = self._current_symbol()
        if self.live_engine is None:
            raise RuntimeError("浜ゆ槗寮曟搸灏氭湭鍒濆鍖?)
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
                raise RuntimeError("浜ゆ槗寮曟搸灏氭湭鍒濆鍖?)

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
                f"鏈€杩戜俊鍙? {decision.signal.value.upper()} @ {decision.reference_price:.2f} | {result.message}"
            )
            self.log(f"鎵ц缁撴灉 | {decision.symbol} | {result.message}")
            if result.order_id:
                self.cancel_order_edit.setText(result.order_id)
            self.sync_broker_state(source="execute_signal")
            self.refresh_records()
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("鎵ц澶辫触", str(exc))

    def cancel_order(self) -> None:
        try:
            order_id = self.cancel_order_edit.text().strip()
            if not order_id:
                raise RuntimeError("璇峰厛杈撳叆瑕佹挙閿€鐨勮鍗曞彿")
            result = self.broker.cancel_order(order_id)
            self.log(f"鎾ゅ崟缁撴灉 | {order_id} | {result.message}")
            self.sync_broker_state(source="cancel_order")
            self.refresh_records()
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("鎾ゅ崟澶辫触", str(exc))

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
            self.last_data_source = str(source)
            self.last_refresh_at = datetime.now().strftime("%H:%M:%S")
            self._refresh_status_labels()
            self.log(f"鍒锋柊琛屾儏鎴愬姛锛屽叡 {len(snapshot)} 鏉★紝鏉ユ簮 {source}")
            self.refresh_positions()
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("鍒锋柊琛屾儏澶辫触", str(exc))

    def refresh_positions(self) -> None:
        try:
            positions = self.broker.get_positions()
            account = self.broker.get_account()
            self.account_label.setText(
                f"璐︽埛: 鐜伴噾 {account.cash:,.2f} | 甯傚€?{account.market_value:,.2f} | 鎬昏祫浜?{account.equity:,.2f}"
            )
            self.position_table.setRowCount(len(positions))
            for row_idx, position in enumerate(positions):
                self._populate_position_row(row_idx, position)
            self.log(f"鍒锋柊鎸佷粨鎴愬姛锛屽叡 {len(positions)} 鏉?)
        except Exception as exc:  # pragma: no cover - UI path
            self._show_error("鍒锋柊鎸佷粨澶辫触", str(exc))

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
            self.log(f"鑷姩鍒锋柊寮傚父: {exc}")

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
                ("accepted", lambda value: "鏄? if int(value) else "鍚?),
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
            raise RuntimeError("璇峰厛閫夋嫨浜ゆ槗鏍囩殑")
        return symbol

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{timestamp}] {message}")

    def _show_error(self, title: str, message: str) -> None:
        self.log(f"{title}: {message}")
        QMessageBox.critical(self, title, message)

