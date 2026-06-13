# ashare-quant-app

一个面向本地运行的 A 股量化交易桌面应用，设计思路参考了 GitHub 上高热度的量化工具：

- `vn.py` 的事件驱动架构、桌面端工作台和网关适配层
- `Backtrader` 的策略与回测分离模式
- `Qlib` 的研究/执行解耦思路
- `AkShare` 的 A 股数据接口生态

第一版目标是做一个可本地运行的桌面量化终端，覆盖以下流程：

- 本地配置管理
- A 股历史数据拉取
- 双均线策略回测
- 实时信号评估
- Dry Run 下单
- QMT/xtquant 实盘适配入口

第二步已经补齐以下能力：

- SQLite 持久化本地记录
- K 线 + 均线图
- 权益曲线图
- 信号、订单、回测记录中心
- 可调策略参数面板

## 技术栈

- Python 3.11+
- PySide6
- pandas / numpy
- akshare
- xtquant（可选，实盘时使用）

## 项目结构

```text
ashare-quant-app
├── config.example.toml
├── pyproject.toml
├── src/ashare_quant_app
│   ├── broker
│   │   ├── base.py
│   │   ├── sim.py
│   │   └── xtquant.py
│   ├── engine
│   │   ├── backtest.py
│   │   └── live.py
│   ├── strategies
│   │   ├── base.py
│   │   └── moving_average.py
│   ├── ui
│   │   └── main_window.py
│   ├── config.py
│   ├── data.py
│   ├── main.py
│   └── models.py
└── tests
    └── test_backtest.py
```

## 安装

```bash
cd /workspace/ashare-quant-app
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 启动桌面应用

```bash
cd /workspace/ashare-quant-app
source .venv/bin/activate
ashare-quant-app
```

## 配置说明

默认配置文件是 `config.example.toml`。

### `risk.dry_run`

- `true`：不实际下单，适合本地验证
- `false`：允许调用券商适配器执行实盘

### `xtquant.enabled`

- `false`：使用本地模拟券商
- `true`：启用 QMT/xtquant 适配器

### `storage.db_path`

- 控制 SQLite 本地数据库文件位置
- 默认值是 `data/ashare_quant_app.db`

## QMT / xtquant 实盘说明

当前代码已提供 `XtQuantBroker` 适配器，用于承接 QMT 的下单、账户和持仓查询逻辑，但你需要满足下面条件：

- 在 Windows 环境安装并登录 MiniQMT/QMT
- 本地 Python 环境已能导入 `xtquant`
- 按券商实际路径配置 `mini_qmt_dir` 和账号参数
- 将 `risk.dry_run = false`
- 将 `xtquant.enabled = true`

由于当前开发沙箱是 Linux 环境，无法在这里直接验证 QMT 实盘链路，所以默认保留为本地 Dry Run 模式。这不会影响代码结构和后续在你的 Windows 交易环境中接入。

## 已实现能力

- `AkshareDataProvider`：拉取 A 股历史日线和实时快照
- `MovingAverageCrossStrategy`：双均线开平仓信号
- `BacktestEngine`：单标的事件驱动回测与基础绩效指标
- `LiveTradingEngine`：实时信号评估与下单流程
- `SimulatedBroker`：本地模拟下单
- `XtQuantBroker`：QMT/xtquant 实盘适配入口
- `MainWindow`：桌面工作台
- `Storage`：SQLite 持久化信号、订单和回测记录
- `PriceChartView`：K 线与均线图
- `EquityChartView`：权益与回撤图

## 第二步界面升级

当前桌面端已经具备这些工作台能力：

- 在主界面直接调整双均线参数和交易股数
- 运行回测后即时显示 K 线/均线和权益曲线
- 每次信号评估自动写入本地 SQLite
- 每次执行信号自动记录订单结果
- 在记录中心查看回测记录、订单记录、信号记录和运行日志

## 后续建议

- 增加更多策略模板，如布林带、动量轮动、因子打分
- 增加成交明细图、收益分布和参数优化结果页
- 增加风控规则，如止损、仓位上限、黑名单
- 增加任务调度和自动轮询
- 为 QMT 增加更多订单状态回报和撤单管理

## 测试

```bash
cd /workspace/ashare-quant-app
source .venv/bin/activate
pytest
```

## GitHub 托管说明

当前沙箱里未安装 `gh`，也没有现成的 GitHub 登录态，所以我不能直接在你的 GitHub 账号下创建远程仓库。

我已经将项目按照仓库名 `ashare-quant-app` 组织好。你只需要在本地或当前环境配置好 GitHub 凭据后执行：

```bash
git init
git add .
git commit -m "feat: initialize ashare quant desktop app"
git branch -M main
git remote add origin https://github.com/<你的用户名>/ashare-quant-app.git
git push -u origin main
```

如果你愿意下一条消息把你的 GitHub 用户名和可用的推送方式告诉我，我可以继续帮你把本地 `git` 初始化和远程地址也一起准备好。
