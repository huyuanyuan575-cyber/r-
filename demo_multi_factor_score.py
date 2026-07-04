"""演示 strategies/multi_factor_score.py：估值 + 动量 + 波动率 长线多因子选股模型。

本沙箱环境无法连通 akshare/百度股市通(网络策略限制)，这里用示例数据演示排名和因子
归因逻辑：行业分类用的是真实公开常识(贵州茅台/五粮液同属白酒)，PE 和价格走势是为了
让排名差异有说服力而设定的示意性数值，不代表真实基本面或行情——真实结论需要用
data.fundamentals + data.fetcher 的真实数据重新跑一遍(把 ohlcv_provider /
fundamentals_provider 参数去掉，用默认的真实数据源即可)。
"""

import numpy as np
import pandas as pd

from strategies.multi_factor_score import score_stocks

SYMBOLS = ["600519", "000858", "601318", "300750", "000001"]
AS_OF_DATE = "2026-07-03"

# 行业分类为真实公开信息；PE为便于演示排名差异的示意性数值，不是实时行情
SAMPLE_FUNDAMENTALS = {
    "600519": {"industry": "白酒", "pe": 22.0, "name": "贵州茅台"},
    "000858": {"industry": "白酒", "pe": 18.0, "name": "五粮液"},
    "601318": {"industry": "保险", "pe": 8.0, "name": "中国平安"},
    "300750": {"industry": "电池", "pe": 35.0, "name": "宁德时代"},
    "000001": {"industry": "银行", "pe": 5.0, "name": "平安银行"},
}

# 示意性走势设定：drift=日均收益率，vol=日收益率标准差，用于制造出有区分度、
# 排名理由说得清楚的示例价格序列
SAMPLE_TREND = {
    "600519": {"drift": 0.0010, "vol": 0.012, "seed": 11},
    "000858": {"drift": -0.0005, "vol": 0.015, "seed": 12},
    "601318": {"drift": 0.0006, "vol": 0.010, "seed": 13},
    "300750": {"drift": 0.0020, "vol": 0.028, "seed": 14},
    "000001": {"drift": 0.0002, "vol": 0.009, "seed": 15},
}


def fake_fundamentals_provider(symbols, date):
    return pd.DataFrame(
        [
            {"symbol": s, "industry": SAMPLE_FUNDAMENTALS[s]["industry"], "pe": SAMPLE_FUNDAMENTALS[s]["pe"]}
            for s in symbols
        ]
    )


def build_trend_ohlcv(symbol: str, date: str, periods: int = 150) -> pd.DataFrame:
    trend = SAMPLE_TREND[symbol]
    rng = np.random.default_rng(trend["seed"])
    dates = pd.bdate_range(end=date, periods=periods)
    daily_returns = trend["drift"] + rng.normal(0, trend["vol"], size=periods)
    closes = 100 * np.cumprod(1 + daily_returns)
    return pd.DataFrame(
        {
            "date": dates,
            "symbol": symbol,
            "open": closes,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": 1_000_000,
            "amount": 100_000_000,
        }
    )


def fake_ohlcv_provider(symbol: str, date: str) -> pd.DataFrame:
    return build_trend_ohlcv(symbol, date)


def explain_row(row) -> str:
    drivers = []
    if row["valuation_zscore"] > 0.3:
        drivers.append(f"估值因子(+{row['valuation_zscore']:.2f})拉高：同行业内PE偏低")
    elif row["valuation_zscore"] < -0.3:
        drivers.append(f"估值因子({row['valuation_zscore']:.2f})拉低：同行业内PE偏高")
    else:
        drivers.append("估值因子中性(同行业内PE接近平均，或该行业只有它一只样本股)")

    if row["momentum_zscore"] > 0.3:
        drivers.append(f"动量因子(+{row['momentum_zscore']:.2f})拉高：过去60日涨幅相对更强")
    elif row["momentum_zscore"] < -0.3:
        drivers.append(f"动量因子({row['momentum_zscore']:.2f})拉低：过去60日涨幅相对更弱")

    if row["volatility_zscore"] > 0.3:
        drivers.append(f"波动率因子(+{row['volatility_zscore']:.2f})拉高：波动相对更低更稳")
    elif row["volatility_zscore"] < -0.3:
        drivers.append(f"波动率因子({row['volatility_zscore']:.2f})拉低：波动相对更高更不稳")

    return "；".join(drivers)


def main():
    result = score_stocks(
        SYMBOLS,
        AS_OF_DATE,
        ohlcv_provider=fake_ohlcv_provider,
        fundamentals_provider=fake_fundamentals_provider,
    )
    result["name"] = result["symbol"].map(lambda s: SAMPLE_FUNDAMENTALS[s]["name"])

    print("=" * 100)
    print("多因子选股排名（行业分类真实，PE/价格走势为示意性数值，不代表真实行情）")
    print("=" * 100)
    cols = [
        "rank", "symbol", "name", "industry", "pe", "momentum60", "volatility60",
        "valuation_zscore", "momentum_zscore", "volatility_zscore", "composite_score",
    ]
    print(result[cols].to_string(index=False))

    print("\n逐个解释排名成因：")
    for _, row in result.iterrows():
        print(f"第{row['rank']}名 {row['symbol']}({row['name']}) 综合得分{row['composite_score']:.3f}：{explain_row(row)}")


if __name__ == "__main__":
    main()
