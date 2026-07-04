# 个人量化交易分析系统

一个用 Python 搭建的个人量化交易分析项目骨架，覆盖数据获取、因子计算、策略、回测、风控与可视化。

## 目录结构

```
.
├── data/            # 数据获取、缓存与清洗
│   ├── raw/         # 从数据源(akshare等)拉取的原始行情数据(增量缓存，csv)
│   ├── cache/       # 中间计算结果缓存(如交易日历)，可随时删除重新生成
│   ├── fetcher.py   # 批量拉取日线OHLCV(前复权)，带本地增量缓存
│   ├── calendar.py  # A股交易日历，用于识别停牌造成的缺失交易日
│   ├── cleaner.py   # 数据清洗：停牌标记为NaN、涨跌停幅度异常值标记
│   └── update.py    # 增量更新脚本：只补齐本地缓存到今天之间缺失的数据
├── factors/         # 技术指标与因子计算
│   └── technical.py # MA/EMA/MACD/RSI/布林带/动量/波动率/量比
├── strategies/       # 选股策略与买卖点信号生成逻辑
│   └── ma_cross_rsi.py # MA5/MA20金叉死叉 + 量能确认 + RSI超买 的买卖点策略
├── backtest/        # 回测引擎：撮合、持仓、绩效统计
├── risk/            # 风控模块：仓位限制、止损止盈、风险指标
├── viz/             # 可视化：K线图、净值曲线、因子分布等
│   ├── plot_signals.py # 在价格走势图上标注买卖点
│   └── output/         # 生成的图表(不入库)
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

## data/ 模块：批量拉取、缓存、清洗、增量更新

```bash
source venv/bin/activate

# 批量拉取 + 缓存 + 清洗效果演示（含停牌/异常涨跌幅的示例对比）
python demo_clean_data.py

# 每日增量更新（只补齐本地缓存最新日期到今天之间的数据，不重新下载全部历史）
python -m data.update
```

- `data.fetcher.batch_fetch_daily_bars(symbols, start_date, end_date)`：批量拉取多只
  股票的日线OHLCV（前复权），已缓存的日期区间不会重复请求接口，请求之间有间隔以降低限流风险。
- `data.cleaner.clean_daily_bars(df, symbol, trade_calendar=...)`：
  - 停牌交易日不会被 0 填充或悄悄丢弃，而是补齐为完整交易日历中的一行，行情字段显式标记为 `NaN`，并置 `is_suspended=True`。
  - 单日涨跌幅超过该股票理论涨跌停限制(主板10%/创业板科创板20%，含容差)的记录会标记 `is_price_anomaly=True`，仅做标记，不自动删除或修正，需要人工复核。
  - **已知限制**：ST/*ST 股票实际涨跌停幅度为5%，当前数据源未附带ST状态，判定阈值统一按非ST股票计算。
- `data.update.main()`（即 `python -m data.update`）：对默认股票列表 `["600519", "000858", "601318", "300750", "000001"]`
  做增量更新，可配合 crontab 每个交易日收盘后运行一次。
- **前复权缓存的已知陷阱**：qfq 价格以最新交易日为基准反算历史价格，标的发生除权除息后
  历史 qfq 价格会整体偏移。增量缓存无法自动感知这类事件，如需严格回测，建议在除权除息
  公告后对相关标的重新全量拉取（`use_cache=False`），详见 `data/fetcher.py` 顶部说明。

本地自测（不依赖真实网络，也不需要安装 pytest）：

```bash
python tests/test_data_pipeline.py
```

## factors/ 模块：技术指标计算

```bash
source venv/bin/activate
python demo_factors.py
python tests/test_factors.py
```

`factors.technical` 提供的函数都接收 `data.cleaner.clean_daily_bars` 清洗后的
DataFrame，直接在停牌日（NaN）上做 rolling/ewm 计算，不做人工填充：

- `moving_average` / `ema`：简单/指数移动平均线
- `macd`：DIF、DEA、MACD柱
- `rsi`：Wilder 平滑 RSI
- `bollinger_bands`：布林带上中下轨
- `momentum`：N日动量(收益率)因子
- `volatility`：N日收益率滚动标准差
- `volume_ratio`：量比(当日成交量/过去N日均量)
- `add_all_factors`：一次性叠加以上全部默认因子

`data.sample_data.build_sample_raw` 是给 `demo_clean_data.py` / `demo_factors.py`
在网络不可用时使用的随机游走示例数据生成器，仅用于验证清洗/因子逻辑本身，不代表
真实行情，正式使用请用 `data.fetcher.batch_fetch_daily_bars` 拉取真实数据。

## strategies/ 模块：MA金叉死叉 + 量能 + RSI 买卖点策略

```bash
source venv/bin/activate
python demo_strategy.py
python tests/test_strategies.py
```

`strategies.ma_cross_rsi.generate_signals(df)` 输入需已带 `ma5/ma20/rsi14/volume_ratio5`
列(即 `factors.technical.add_all_factors` 的输出)，输出新增 `signal` 列：

- **BUY**：当日 MA5 上穿 MA20(金叉)，且当日成交量 > 过去5日平均成交量的1.5倍
- **SELL**：当日 MA5 下穿 MA20(死叉)，或者当日 RSI14 > 80(超买)；同一天两种条件都满足时优先判 SELL
- 其余 **HOLD**；指标历史不足(NaN)的交易日一律 HOLD

**无未来函数**：金叉/死叉只比较当天与前一天的 MA5-MA20 差值符号，量比/RSI 也只用当日及
之前的数据滚动计算，整个函数不含任何 `shift(-1)` 之类的向未来看操作。
`tests/test_strategies.py::test_no_look_ahead_bias` 专门验证了这一点：把数据截断到
第 t 天重新算一遍信号，与用完整数据算出的第 t 天信号必须完全一致——如果偷看了未来
数据，这个测试会失败。

`demo_strategy.py` 会尝试拉取真实茅台近一年数据，网络不可用时回退到示例数据（仅演示
流程，不代表真实行情），打印全部触发的 BUY/SELL 信号日期，并调用
`viz.plot_signals.plot_price_with_signals` 把买卖点画在价格走势图上，保存到
`viz/output/600519_signals.png`。

## 后续规划

- `factors/`: 后续可以补充基本面因子(市盈率/市净率等)、多因子打分/排序
- `strategies/`: 可以补充仓位管理(而不仅是信号)、多股票组合选股
- `backtest/`: 事件驱动或向量化回测引擎，把 strategies 的信号接入撮合和绩效统计
- `risk/`: 仓位管理与止损止盈规则
- `viz/`: 补充K线图(蜡烛图)、净值曲线绘制
