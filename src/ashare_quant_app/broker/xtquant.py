from __future__ import annotations

from pathlib import Path

from ashare_quant_app.broker.base import Broker
from ashare_quant_app.config import XtQuantConfig
from ashare_quant_app.models import AccountSnapshot, OrderRequest, OrderResult, Position, Signal


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

    def place_order(self, request: OrderRequest) -> OrderResult:
        self._ensure_connected()

        if request.side not in {Signal.BUY, Signal.SELL}:
            return OrderResult(accepted=False, message="xtquant 仅支持买入或卖出")

        order_type = self._resolve_order_type(request.side)
        xt_order_id = self._xt_trader.order_stock(
            self._stock_account,
            request.symbol,
            order_type,
            int(request.volume),
            23,  # 23 = 限价
            float(request.price),
            request.note or "ashare-quant-app",
        )

        if xt_order_id in (None, -1):
            return OrderResult(accepted=False, message="xtquant 下单失败")

        return OrderResult(
            accepted=True,
            message=f"xtquant 下单成功: {request.side.value} {request.symbol} {request.volume}",
            order_id=str(xt_order_id),
        )

    def _resolve_order_type(self, side: Signal) -> int:
        from xtquant import xtconstant

        if side == Signal.BUY:
            return getattr(xtconstant, "STOCK_BUY")
        return getattr(xtconstant, "STOCK_SELL")

    def _ensure_connected(self) -> None:
        if not self.connected or self._xt_trader is None or self._stock_account is None:
            raise RuntimeError("xtquant 尚未连接，请先执行 connect()")
