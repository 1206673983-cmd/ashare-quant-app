from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ashare_quant_app.broker.base import Broker
from ashare_quant_app.config import XtQuantConfig
from ashare_quant_app.models import (
    AccountSnapshot,
    BrokerEvent,
    BrokerOrder,
    EventLevel,
    OrderRequest,
    OrderResult,
    OrderStatus,
    Position,
    Signal,
    TradeFill,
)


class XtQuantBroker(Broker):
    """Thin wrapper around xtquant/QMT.

    This adapter is intentionally defensive because QMT deployments differ by
    local installation, xtquant package version, and broker account type.
    """

    def __init__(self, config: XtQuantConfig) -> None:
        self.config = config
        self.connected = False
        self._xt_trader = None
        self._stock_account = None
        self._events: list[BrokerEvent] = []

    def connect(self) -> None:
        if not self.config.enabled:
            raise RuntimeError("xtquant 未启用，请在配置文件中将 xtquant.enabled 设为 true")

        if self.config.client_path and not Path(self.config.client_path).exists():
            raise FileNotFoundError(f"QMT 客户端路径不存在: {self.config.client_path}")

        try:
            from xtquant import xtconstant
            from xtquant.xttrader import XtQuantTrader
            from xtquant.xttype import StockAccount
        except ImportError as exc:
            raise RuntimeError(
                "当前环境未安装 xtquant。A股 QMT 实盘通常需要 Windows + MiniQMT/QMT 本地环境。"
            ) from exc

        self._xt_trader = XtQuantTrader(self.config.mini_qmt_dir, self.config.session_id)
        self._stock_account = StockAccount(
            self.config.account_id,
            getattr(xtconstant, "SECURITY_ACCOUNT"),
        )

        started = self._xt_trader.start()
        if started is False:
            raise RuntimeError("xtquant 交易线程启动失败")

        connected = self._xt_trader.connect()
        if connected is False:
            raise RuntimeError("xtquant 连接失败，请检查 QMT/MiniQMT 是否已登录")

        subscribed = self._xt_trader.subscribe(self._stock_account)
        if subscribed is False:
            raise RuntimeError("xtquant 账户订阅失败")

        self.connected = True
        self._record_event(EventLevel.INFO, "connection", "xtquant 连接并订阅成功")

    def get_account(self) -> AccountSnapshot:
        self._ensure_connected()
        asset = self._xt_trader.query_stock_asset(self._stock_account)
        market_value = float(getattr(asset, "market_value", 0.0))
        cash = float(getattr(asset, "cash", 0.0))
        total = float(getattr(asset, "total_asset", cash + market_value))
        return AccountSnapshot(cash=cash, equity=total, market_value=market_value)

    def get_positions(self) -> list[Position]:
        self._ensure_connected()
        positions = []
        for item in self._xt_trader.query_stock_positions(self._stock_account):
            positions.append(
                Position(
                    symbol=str(getattr(item, "stock_code", "")),
                    volume=int(getattr(item, "volume", 0)),
                    available_volume=int(getattr(item, "can_use_volume", 0)),
                    avg_price=float(getattr(item, "open_price", 0.0)),
                    last_price=float(getattr(item, "last_price", 0.0)),
                )
            )
        return positions

    def get_orders(self) -> list[BrokerOrder]:
        self._ensure_connected()
        orders = []
        query_fn = getattr(self._xt_trader, "query_stock_orders", None)
        if query_fn is None:
            return orders
        for item in query_fn(self._stock_account) or []:
            status_value = str(getattr(item, "order_status", "")).lower()
            status = self._map_status(status_value)
            orders.append(
                BrokerOrder(
                    order_id=str(getattr(item, "order_id", "")),
                    symbol=str(getattr(item, "stock_code", "")),
                    side=Signal.BUY if "buy" in str(getattr(item, "order_type", "")).lower() else Signal.SELL,
                    price=float(getattr(item, "price", 0.0)),
                    volume=int(getattr(item, "order_volume", 0)),
                    filled_volume=int(getattr(item, "traded_volume", 0)),
                    status=status,
                    message=str(getattr(item, "status_msg", "")),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
            )
        return orders

    def get_trades(self) -> list[TradeFill]:
        self._ensure_connected()
        trades = []
        query_fn = getattr(self._xt_trader, "query_stock_trades", None)
        if query_fn is None:
            return trades
        for item in query_fn(self._stock_account) or []:
            trades.append(
                TradeFill(
                    trade_id=str(getattr(item, "traded_id", "")),
                    order_id=str(getattr(item, "order_id", "")),
                    symbol=str(getattr(item, "stock_code", "")),
                    side=Signal.BUY if "buy" in str(getattr(item, "order_type", "")).lower() else Signal.SELL,
                    price=float(getattr(item, "traded_price", 0.0)),
                    volume=int(getattr(item, "traded_volume", 0)),
                )
            )
        return trades

    def get_events(self) -> list[BrokerEvent]:
        return sorted(self._events, key=lambda item: item.created_at, reverse=True)

    def update_market_prices(self, prices: dict[str, float]) -> None:
        # QMT account assets/positions are queried from the client; no local state update is needed here.
        return None

    def place_order(self, request: OrderRequest) -> OrderResult:
        self._ensure_connected()

        if request.side not in {Signal.BUY, Signal.SELL}:
            return OrderResult(accepted=False, message="xtquant 仅支持买入或卖出", status=OrderStatus.REJECTED)

        order_type = self._resolve_order_type(request.side)
        try:
            xt_order_id = self._xt_trader.order_stock(
                self._stock_account,
                request.symbol,
                order_type,
                int(request.volume),
                23,  # 23 = 限价
                float(request.price),
                request.note or "ashare-quant-app",
            )
        except Exception as exc:
            self._record_event(EventLevel.ERROR, "order", f"xtquant 下单异常: {exc}")
            return OrderResult(accepted=False, message=f"xtquant 下单异常: {exc}", status=OrderStatus.REJECTED)

        if xt_order_id in (None, -1):
            self._record_event(EventLevel.ERROR, "order", "xtquant 下单失败")
            return OrderResult(accepted=False, message="xtquant 下单失败", status=OrderStatus.REJECTED)

        self._record_event(
            EventLevel.INFO,
            "order",
            f"xtquant 下单成功: {request.side.value} {request.symbol} {request.volume} @ {request.price:.2f}",
        )

        return OrderResult(
            accepted=True,
            message=f"xtquant 下单成功: {request.side.value} {request.symbol} {request.volume}",
            order_id=str(xt_order_id),
            status=OrderStatus.SUBMITTED,
        )

    def cancel_order(self, order_id: str) -> OrderResult:
        self._ensure_connected()
        cancel_fn = getattr(self._xt_trader, "cancel_order_stock", None)
        if cancel_fn is None:
            return OrderResult(accepted=False, message="当前 xtquant 版本不支持撤单接口", order_id=order_id)
        try:
            result = cancel_fn(self._stock_account, int(order_id))
        except Exception as exc:
            self._record_event(EventLevel.ERROR, "order", f"xtquant 撤单异常: {exc}")
            return OrderResult(accepted=False, message=f"xtquant 撤单异常: {exc}", order_id=order_id)
        if result in (None, -1, False):
            self._record_event(EventLevel.ERROR, "order", f"xtquant 撤单失败: {order_id}")
            return OrderResult(accepted=False, message="xtquant 撤单失败", order_id=order_id)
        self._record_event(EventLevel.WARNING, "order", f"xtquant 撤单成功: {order_id}")
        return OrderResult(
            accepted=True,
            message="xtquant 撤单成功",
            order_id=order_id,
            status=OrderStatus.CANCELLED,
        )

    def _resolve_order_type(self, side: Signal) -> int:
        from xtquant import xtconstant

        if side == Signal.BUY:
            return getattr(xtconstant, "STOCK_BUY")
        return getattr(xtconstant, "STOCK_SELL")

    def _map_status(self, raw_status: str) -> OrderStatus:
        if "cancel" in raw_status:
            return OrderStatus.CANCELLED
        if "fill" in raw_status or "trade" in raw_status:
            return OrderStatus.FILLED
        if "reject" in raw_status or "fail" in raw_status:
            return OrderStatus.REJECTED
        if "partial" in raw_status:
            return OrderStatus.PARTIAL
        return OrderStatus.SUBMITTED

    def _record_event(self, level: EventLevel, category: str, message: str) -> None:
        self._events.append(BrokerEvent(level=level, category=category, message=message))

    def _ensure_connected(self) -> None:
        if not self.connected or self._xt_trader is None or self._stock_account is None:
            raise RuntimeError("xtquant 尚未连接，请先执行 connect()")
