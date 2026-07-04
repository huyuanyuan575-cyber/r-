---
name: tushare-data
description: 在本量化项目中通过 Tushare 拉取行情/财务数据时使用。涵盖 token 配置、pro_api 常用接口(日线、复权、财务、指数、基本面)、频率限制与积分门槛、以及与本项目 data/config 目录的约定写法。触发词："tushare"、"拉数据"、"日线"、"财务数据"、"股票数据源"。
---

# Tushare 数据接入指南

本项目的数据源之一是 [Tushare Pro](https://tushare.pro)。使用前必须先在
tushare.pro 注册账号并获取 token（部分接口需要积分才能调用，注册后在
个人主页 -> 接口TOKEN 查看）。

## Token 配置约定

Token 是密钥，**不要硬编码在代码里，也不要提交到仓库**。本项目约定：

1. 复制 `config/secrets.example.py` 为 `config/secrets.py`（已在 `.gitignore` 中排除）。
2. 在 `config/secrets.py` 中填入：
   ```python
   TUSHARE_TOKEN = "你的真实token"
   ```
3. 代码里统一这样初始化：
   ```python
   import tushare as ts
   from config.secrets import TUSHARE_TOKEN

   ts.set_token(TUSHARE_TOKEN)
   pro = ts.pro_api()
   ```
   如果 `config/secrets.py` 还不存在（比如全新环境），先提示用户复制模板文件并填入 token，
   不要用假 token 尝试请求。

## 常用接口速查

- `pro.daily(ts_code="600519.SH", start_date="20240101", end_date="20241231")`
  日线行情（未复权），字段：open/high/low/close/vol/amount 等。
- `ts.pro_bar(ts_code="600519.SH", adj="qfq", start_date=..., end_date=...)`
  带前复权/后复权的日线，比 `pro.daily` 更适合做回测（复权价格连续）。
- `pro.daily_basic(ts_code="600519.SH", trade_date="20241231")`
  每日指标：市盈率、市净率、换手率、总市值等基本面因子。
- `pro.index_daily(ts_code="000300.SH", ...)`
  指数日线，常用于基准对比（沪深300等）。
- `pro.fina_indicator(ts_code="600519.SH")`
  财务指标（ROE、毛利率等），用于基本面因子。
- `ts_code` 格式为 `代码.交易所后缀`：沪市 `.SH`，深市 `.SZ`。akshare 的
  6 位代码（如 `600519`）需要拼接后缀才能传给 tushare 接口。

## 频率限制与积分

- 免费账号有单分钟调用次数限制，且部分接口（如高频、分钟线、财务数据的部分字段）
  需要累计积分才能访问，调用超限会抛出异常或返回空数据，注意捕获并给出清晰提示，
  不要静默重试导致触发风控。
- 长期本地开发建议对高频重复请求的数据做本地缓存（写入 `data/cache/`），
  避免重复消耗调用额度。

## 与项目目录的约定

- 原始数据落地到 `data/raw/`，文件名建议 `{ts_code去掉后缀}_daily.csv`，
  与 akshare 版本的 demo（`demo_fetch_data.py`）保持一致的命名风格，方便下游
  `factors/` 模块统一读取。
- 中间衍生数据（例如已经计算过复权、拼接过多只股票）放 `data/cache/`。
- 拉取逻辑本身不要写进 `factors/` 或 `strategies/`，保持数据获取与因子/策略计算分层。

## 环境限制提示

若当前运行环境的出站网络受策略限制（例如沙箱环境只放行少数域名），
`api.tushare.pro` 可能无法连通。遇到网络策略拒绝（403/407）时，如实告知
用户这是网络策略限制，不要尝试绕过代理或更换协议规避策略；建议用户在
本地无限制的机器上运行。
