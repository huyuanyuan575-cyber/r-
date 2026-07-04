# 个人量化交易分析系统

一个用 Python 搭建的个人量化交易分析项目骨架，覆盖数据获取、因子计算、策略、回测、风控与可视化。

## 目录结构

```
.
├── data/            # 原始数据与缓存
│   ├── raw/         # 从数据源(akshare等)拉取的原始行情数据
│   └── cache/       # 中间计算结果缓存，可随时删除重新生成
├── factors/         # 技术指标与因子计算(如均线、MACD、动量因子等)
├── strategies/       # 选股策略与买卖点信号生成逻辑
├── backtest/        # 回测引擎：撮合、持仓、绩效统计
├── risk/            # 风控模块：仓位限制、止损止盈、风险指标
├── viz/             # 可视化：K线图、净值曲线、因子分布等
├── config/          # 配置：数据源密钥、回测参数等
│   ├── settings.py           # 非敏感参数配置
│   └── secrets.example.py    # 密钥模板，复制为 secrets.py 后填入真实值(已被 .gitignore 排除)
├── tests/           # 单元测试
├── demo_fetch_data.py          # Demo: 用 akshare 拉取贵州茅台日线数据并存为 csv
├── demo_fetch_data_tushare.py  # Demo: 用 Tushare Pro 拉取贵州茅台日线数据并存为 csv
├── requirements.txt
└── venv/            # Python 虚拟环境(不入库)
```

## 环境搭建

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 运行 Demo

```bash
source venv/bin/activate
python demo_fetch_data.py
```

脚本会通过 akshare 拉取贵州茅台(600519)最近一年的日线数据，保存到
`data/raw/600519_daily.csv`，并打印前 5 行用于确认数据可用。

### Tushare 数据源

项目同时接入了 [Tushare Pro](https://tushare.pro) 作为第二数据源，用法见
`.claude/skills/tushare-data/SKILL.md`。使用前需要：

```bash
cp config/secrets.example.py config/secrets.py
# 编辑 config/secrets.py，填入你在 tushare.pro 个人主页获取的 TUSHARE_TOKEN

source venv/bin/activate
python demo_fetch_data_tushare.py
```

脚本会保存到 `data/raw/600519_daily_tushare.csv`。

## 后续规划

- `factors/`: 实现常用技术指标(MA、MACD、RSI等)与自定义因子
- `strategies/`: 基于因子的选股与择时策略
- `backtest/`: 事件驱动或向量化回测引擎
- `risk/`: 仓位管理与止损止盈规则
- `viz/`: 基于 matplotlib 的K线图、净值曲线绘制
