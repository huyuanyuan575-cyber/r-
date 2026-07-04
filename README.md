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
│   ├── update.py    # 增量更新脚本：只补齐本地缓存到今天之间缺失的数据
│   └── fundamentals.py # 行业分类 + PE(TTM)获取，供多因子选股模型使用
├── factors/         # 技术指标与因子计算
│   └── technical.py # MA/EMA/MACD/RSI/布林带/动量/波动率/量比
├── strategies/       # 选股策略与买卖点信号生成逻辑
│   ├── ma_cross_rsi.py       # MA5/MA20金叉死叉 + 量能确认 + RSI超买 的买卖点策略
│   └── multi_factor_score.py # 估值(行业内PE)+动量+波动率 多因子长线选股打分
├── backtest/        # 回测引擎：撮合、持仓、绩效统计
│   └── engine.py    # 单标的回测：手续费+滑点+T+1+涨跌停+仓位限制，输出净值曲线与指标
├── risk/            # 风控模块：仓位限制、止损止盈、组合回撤熔断
│   └── rules.py     # RiskConfig：止损/止盈(分批减仓)/组合回撤熔断参数，供backtest引擎使用
├── viz/             # 可视化：K线图、净值曲线、因子分布等
│   ├── plot_signals.py # 在价格走势图上标注买卖点
│   ├── plot_equity.py  # 绘制回测净值曲线(含最大回撤区间标注)
│   ├── app.py           # Streamlit 页面1：股票走势+指标+信号
│   ├── pages/           # Streamlit 页面2/3：多因子选股排名、回测报告
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

## strategies/ 模块：估值 + 动量 + 波动率 多因子长线选股

```bash
source venv/bin/activate
python demo_multi_factor_score.py
python tests/test_multi_factor_score.py
```

`strategies.multi_factor_score.score_stocks(symbols, date, weights=None)` 输入一批
股票代码和日期，输出这一天所有股票的因子得分与排名：

- **valuation(估值)**：PE(TTM)，越低越好，在**同行业内**做 zscore(-PE)（不跨行业比较
  绝对估值高低，因为不同行业合理估值中枢本来不同）；某行业若只有1只样本股，无从比较，记为中性0
- **momentum(动量)**：过去60个交易日涨幅，越高越好，在整个输入股票池内做 zscore
- **volatility(波动率)**：过去60个交易日收益率标准差，越低越好，在整个股票池内做 zscore(-波动率)
- 三项按权重(默认各1/3)加权求和得到 `composite_score`，从高到低排名

新增 `data.fundamentals` 模块负责真实基本面数据：`get_industry`(东方财富个股信息，
只能取当前分类) + `get_pe_on_date`(百度股市通历史PE(TTM)序列)，两者都做了本地缓存。
`score_stocks` 的 `ohlcv_provider`/`fundamentals_provider` 参数可替换默认的真实数据源，
`demo_multi_factor_score.py` 就是用这两个参数换成示例数据演示的（行业分类是真实公开
信息，PE和价格走势为示意性数值，不代表真实行情——正式使用时不传这两个参数即可，
自动走真实的 `data.fetcher`/`data.fundamentals`）。

## backtest/ 模块：单标的回测引擎(交易成本+滑点+T+1+涨跌停+仓位限制)

```bash
source venv/bin/activate
python demo_backtest.py
python tests/test_backtest.py
```

`backtest.engine.run_backtest(signal_df, symbol, initial_capital=100_000, max_position_pct=0.2)`
输入 `strategies` 产出的信号表(date/close/pct_chg/signal)，模拟以下真实交易约束：

- 交易成本：买入手续费万3；卖出手续费万3 + 印花税千1
- 滑点：按成交价上下浮动0.1%(买入更贵、卖出更便宜地成交)
- A股 T+1：当天买入的股票当天不能卖出
- 涨跌停：当天涨跌幅达到该股票理论涨跌停幅度(复用 `data.cleaner.price_limit_pct`)时，
  对应方向视为无法成交(涨停不能买/跌停不能卖)
- 仓位限制：单次买入不超过当前总资产的 `max_position_pct`，且按A股100股一手取整

返回 `BacktestResult(equity_curve, trades, metrics)`，`metrics` 含年化收益率、最大回撤
(及起止日期)、夏普比率、胜率、盈亏比、交易次数；`backtest.engine.format_report()` 输出
文字报告，`viz.plot_equity.plot_equity_curve()` 画净值曲线并标出最大回撤区间。

**一个跑真实数据大概率会遇到的真实问题**：贵州茅台股价高(~1200-2400元/股)，A股100股
一手，`demo_backtest.py` 用10万本金+20%仓位上限跑示例数据时发现**买1手都不够钱**
(20%×10万=2万，但100股要花17万+)，导致0笔交易——这不是策略或引擎的问题，是"高价股+
100股一手+这个仓位上限+这个本金"组合本身的资金约束问题，值得在正式使用前想清楚(调大
本金、放宽仓位上限、或只用于低价股)。`demo_backtest.py` 里额外跑了一段手工构造的
"引擎自检"序列，证明整套回测机制在能正常成交的情况下是通的。

## risk/ 模块：止损止盈 + 组合回撤熔断(整合进回测引擎)

```bash
source venv/bin/activate
python demo_risk_backtest.py
python tests/test_risk.py
```

`risk.rules.RiskConfig` 定义规则参数，传给 `backtest.engine.run_backtest(..., risk_config=...)`
即可叠加风控，动作优先级为 **止损 > 止盈(分批减仓) > 策略自身SELL信号 > 策略自身BUY信号**：

- `stop_loss_pct`(默认8%)：单只股票浮亏超过这个比例，无论策略信号是什么都强制卖出剩余全部持仓
- `take_profit_pct` / `take_profit_reduce_ratio`(默认30% / 0.5)：浮盈超过阈值时卖出对应比例的
  持仓(分批减仓)；每笔持仓生命周期只触发一次，不会因为浮盈继续走高而反复减仓
- `portfolio_drawdown_halt_pct`(默认15%)：账户总资产相对历史最高点回撤超过这个比例时，
  暂停开新仓(BUY)，但止损/止盈/策略SELL这些平仓动作不受影响，仍然允许

`Trade` 增加了 `exit_reason` 字段(`STOP_LOSS`/`TAKE_PROFIT`/`SIGNAL_SELL`)，方便区分每笔
平仓到底是被风控强制平的还是策略自己决定卖的。

**一个值得知道的真实局限**：止损/止盈依然受涨跌停规则约束——跌停当天没有对手买盘，
即使触发了止损条件也没法在当天卖出成交，会顺延到跌停解除的下一天才能真正止损，实盘中
下跌超预期时止损同样可能失效，这不是本引擎的bug，是A股涨跌停制度本身的真实局限。

`demo_risk_backtest.py` 用一段手工构造的多周期涨跌行情(价格亲民、明确制造出金叉+放量，
真实茅台数据同样会遇到 `backtest/` 一节提到的"股价太高买不起1手"问题，所以这里没有直接
用真实茅台价位)对比了"阶段5纯策略信号"和"阶段6叠加风控"两次回测：

| | 无风控 | 加风控 |
|---|---|---|
| 最大回撤 | -1.95% | -1.20% |
| 年化收益率 | 29.64% | 28.41% |
| 交易次数 | 6 | 13 |

这次示例里，风控让最大回撤更小(止盈提前锁定部分收益，减少了单笔持仓的回撤敞口)，代价
是年化收益略微降低(止盈在+30%就卖出一半，比等死叉信号卖出全部少赚一点)——**回撤没有
改善多少、收益也没降多少的原因是这段示例行情本身比较温和，没有真正触发止损**(0笔
`STOP_LOSS`，全部是 `TAKE_PROFIT`/`SIGNAL_SELL`)。风控规则真正的价值在真实数据里遇到
急跌行情时才能体现，用示例数据看不出"哪个更好"的决定性结论，需要用真实数据重新跑一遍
才能下真实判断。

## viz/ 模块：Streamlit 本地网页界面

```bash
source venv/bin/activate
streamlit run viz/app.py
```

启动后浏览器会自动打开(默认 http://localhost:8501)，左侧栏可以在3个页面间切换：

- **页面1(app / 首页)**：输入股票代码，展示价格走势图 + 技术指标表 + 买卖信号标注
  (`viz/app.py`)
- **页面2(多因子选股)**：输入股票代码列表和日期，展示多因子排名表——Streamlit的
  表格原生支持点击列名排序，不需要额外代码(`viz/pages/2_多因子选股.py`)
- **页面3(回测报告)**：设置初始资金/仓位上限，可选叠加风控规则(止损/止盈/回撤熔断)，
  展示回测关键指标、净值曲线、交易明细(`viz/pages/3_回测报告.py`)

三个页面都会先尝试拉取真实数据，网络不可用时(比如本沙箱环境)会自动回退到示例数据并
在页面上用黄色提示条标注"当前展示的是示例数据"，不会静默地把示例数据当真实结果展示。
已经用 Playwright 无头浏览器实际跑起来验证过三个页面都能正常渲染、交互(输入代码查询、
点击"计算排名"、点击"运行回测")。

## 后续规划

- `factors/`: 后续可以补充更多基本面因子(市净率/ROE等)
- `strategies/`: 可以补充仓位管理(而不仅是信号)、组合层面的选股+择时结合
- `viz/`: 补充K线图(蜡烛图)
