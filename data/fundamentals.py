"""估值(PE)与行业分类数据获取，供多因子选股模型使用。

数据源：
- 行业分类：东方财富个股信息接口(akshare.stock_individual_info_em)，只能取到"当前"
  分类，不能追溯历史某一天的行业归属——对个人量化分析而言，行业分类变动频率很低，
  用当前分类近似历史某天通常可以接受，但严格意义上不是历史真值。
- PE(TTM)：百度股市通历史估值接口(akshare.stock_zh_valuation_baidu)，取指定日期
  (或该日期之前最近一个有数据的交易日)的市盈率(TTM)。

本地缓存：行业分类变化很慢，缓存到 data/cache/industry_map.csv，默认长期复用；
PE 序列缓存到 data/cache/{symbol}_pe_baidu.csv，每次调用若已存在缓存直接复用，
避免重复请求(如需刷新传 force_refresh=True)。
"""

import akshare as ak
import pandas as pd

from config.settings import DATA_CACHE_DIR

_INDUSTRY_CACHE_PATH = DATA_CACHE_DIR / "industry_map.csv"


def get_industry(symbol: str, force_refresh: bool = False) -> str:
    """获取股票所属行业(东方财富分类，当前时点)。"""
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not force_refresh and _INDUSTRY_CACHE_PATH.exists():
        cached = pd.read_csv(_INDUSTRY_CACHE_PATH, dtype=str)
        hit = cached[cached["symbol"] == symbol]
        if not hit.empty:
            return hit["industry"].iloc[0]
    else:
        cached = pd.DataFrame(columns=["symbol", "industry"])

    info = ak.stock_individual_info_em(symbol=symbol)
    row = info[info["item"] == "行业"]
    industry = row["value"].iloc[0] if not row.empty else "未知"

    cached = pd.concat(
        [cached[cached["symbol"] != symbol], pd.DataFrame([{"symbol": symbol, "industry": industry}])],
        ignore_index=True,
    )
    cached.to_csv(_INDUSTRY_CACHE_PATH, index=False)
    return industry


def _pe_cache_path(symbol: str):
    return DATA_CACHE_DIR / f"{symbol}_pe_baidu.csv"


def get_pe_series(symbol: str, force_refresh: bool = False) -> pd.DataFrame:
    """获取某股票历史 市盈率(TTM) 序列，列: date, pe。"""
    path = _pe_cache_path(symbol)
    if not force_refresh and path.exists():
        df = pd.read_csv(path, parse_dates=["date"])
        return df

    df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator="市盈率(TTM)", period="近一年")
    df = df.rename(columns={"value": "pe"})
    df["date"] = pd.to_datetime(df["date"])

    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def get_pe_on_date(symbol: str, date: str) -> float | None:
    """取某股票在给定日期(或之前最近一个有数据的交易日)的 PE(TTM)。"""
    df = get_pe_series(symbol)
    target = pd.Timestamp(date)
    valid = df[df["date"] <= target]
    if valid.empty:
        return None
    return float(valid.sort_values("date").iloc[-1]["pe"])


def get_fundamentals_snapshot(symbols: list[str], date: str) -> pd.DataFrame:
    """批量获取一批股票在给定日期的 行业 + PE(TTM) 快照，列: symbol, industry, pe。"""
    rows = []
    for symbol in symbols:
        rows.append(
            {
                "symbol": symbol,
                "industry": get_industry(symbol),
                "pe": get_pe_on_date(symbol, date),
            }
        )
    return pd.DataFrame(rows)
