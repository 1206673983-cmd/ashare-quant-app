from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import tomllib


@dataclass(slots=True)
class DataConfig:
    provider: str = "akshare"
    default_symbols: list[str] = field(default_factory=lambda: ["600519", "000001"])
    start_date: str = "2022-01-01"
    end_date: str = "2026-01-01"
    adjust: str = "qfq"


@dataclass(slots=True)
class StrategyConfig:
    name: str = "moving_average_cross"
    fast_window: int = 5
    slow_window: int = 20
    trade_size: int = 100


@dataclass(slots=True)
class RiskConfig:
    max_position_pct: float = 0.3
    dry_run: bool = True


@dataclass(slots=True)
class XtQuantConfig:
    enabled: bool = False
    account_id: str = ""
    account_type: str = "stock"
    client_path: str = ""
    mini_qmt_dir: str = ""
    session_id: int = 1001


@dataclass(slots=True)
class StorageConfig:
    db_path: str = "data/ashare_quant_app.db"


@dataclass(slots=True)
class AppConfig:
    data: DataConfig = field(default_factory=DataConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    xtquant: XtQuantConfig = field(default_factory=XtQuantConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)

    @classmethod
    def from_file(cls, file_path: str | Path) -> "AppConfig":
        raw = tomllib.loads(Path(file_path).read_text(encoding="utf-8"))
        return cls(
            data=DataConfig(**raw.get("data", {})),
            strategy=StrategyConfig(**raw.get("strategy", {})),
            risk=RiskConfig(**raw.get("risk", {})),
            xtquant=XtQuantConfig(**raw.get("xtquant", {})),
            storage=StorageConfig(**raw.get("storage", {})),
        )

    def to_dict(self) -> dict:
        return asdict(self)
