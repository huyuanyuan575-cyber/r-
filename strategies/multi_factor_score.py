"""长线多因子选股模型：估值 + 动量 + 波动率，标准化加权合成综合得分。

因子定义：
    valuation(估值)：PE(TTM)，越低越好，在同行业内做 zscore(-PE)（行业内相对排名，
        不与其他行业的股票直接比较估值高低，因为不同行业合理估值中枢本来就不同）。
    momentum(动量)：过去60个交易日收盘价涨幅，越高越好，在输入的股票池内整体做 zscore。
    volatility(波动率)：过去60个交易日日收益率的滚动标准差，越低越好，在输入的股票池内
        整体做 zscore(-波动率)。

三个 zscore 按权重加权求和得到 composite_score，得分越高排名越靠前。
"""

import numpy as np
import pandas as pd

from data.cleaner import clean_daily_bars
from data.fetcher import fetch_daily_bars
from data.fundamentals import get_fundamentals_snapshot
from factors.technical import momentum, volatility

DEFAULT_WEIGHTS = {"valuation": 1 / 3, "momentum": 1 / 3, "volatility": 1 / 3}


def _zscore(series: pd.Series) -> pd.Series:
    """整体zscore；标准差为0或样本不足时(无法区分相对高低)返回0，视为中性。"""
    std = series.std()
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def _industry_zscore(series: pd.Series, industry: pd.Series) -> pd.Series:
    """行业内zscore；某行业只有1只股票时无从比较，该股票该项记0(中性)。"""
    frame = pd.DataFrame({"value": series, "industry": industry})
    return frame.groupby("industry")["value"].transform(_zscore)


def _default_ohlcv_provider(symbol: str, date: str, lookback_days: int = 150) -> pd.DataFrame:
    """默认OHLCV数据源：拉取 date 往前 lookback_days 自然日的日线，保证有≥60个交易日历史。"""
    end = pd.Timestamp(date)
    start = end - pd.Timedelta(days=lookback_days)
    return fetch_daily_bars(symbol, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))


def _momentum_and_volatility_as_of(
    symbol: str, date: str, ohlcv_provider, window: int = 60
) -> tuple[float, float]:
    raw_df = ohlcv_provider(symbol, date)
    if raw_df is None or raw_df.empty:
        return np.nan, np.nan

    cleaned = clean_daily_bars(raw_df, symbol=symbol)
    factor_df = momentum(cleaned, window=window)
    factor_df = volatility(factor_df, window=window)

    as_of = factor_df[factor_df["date"] <= pd.Timestamp(date)].sort_values("date")
    if as_of.empty:
        return np.nan, np.nan

    last_row = as_of.iloc[-1]
    return last_row[f"momentum{window}"], last_row[f"volatility{window}"]


def score_stocks(
    symbols: list[str],
    date: str,
    weights: dict | None = None,
    ohlcv_provider=None,
    fundamentals_provider=None,
    window: int = 60,
) -> pd.DataFrame:
    """输入一批股票代码和日期，输出这一天所有股票的因子得分与排名。

    ohlcv_provider(symbol, date) -> DataFrame：可替换默认的真实拉取逻辑，便于用示例
    数据测试；fundamentals_provider(symbols, date) -> DataFrame(symbol, industry, pe)：
    同理可替换默认的 data.fundamentals.get_fundamentals_snapshot。
    """
    weights = weights or DEFAULT_WEIGHTS
    ohlcv_provider = ohlcv_provider or _default_ohlcv_provider
    fundamentals_provider = fundamentals_provider or get_fundamentals_snapshot

    fundamentals = fundamentals_provider(symbols, date).set_index("symbol").reindex(symbols).reset_index()

    momentum_vals, volatility_vals = [], []
    for symbol in symbols:
        m, v = _momentum_and_volatility_as_of(symbol, date, ohlcv_provider, window=window)
        momentum_vals.append(m)
        volatility_vals.append(v)

    result = fundamentals.copy()
    result[f"momentum{window}"] = momentum_vals
    result[f"volatility{window}"] = volatility_vals

    result["valuation_zscore"] = _industry_zscore(-result["pe"], result["industry"])
    result["momentum_zscore"] = _zscore(result[f"momentum{window}"])
    result["volatility_zscore"] = _zscore(-result[f"volatility{window}"])

    result["composite_score"] = (
        weights["valuation"] * result["valuation_zscore"]
        + weights["momentum"] * result["momentum_zscore"]
        + weights["volatility"] * result["volatility_zscore"]
    )

    result = result.sort_values("composite_score", ascending=False).reset_index(drop=True)
    result.insert(0, "rank", result.index + 1)
    return result
