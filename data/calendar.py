"""A股交易日历，用于把行情数据对齐到标准交易日，从而识别停牌造成的缺失日期。"""

import akshare as ak
import pandas as pd

from config.settings import DATA_CACHE_DIR

_CALENDAR_CACHE_PATH = DATA_CACHE_DIR / "trade_calendar.csv"


def get_trade_calendar(start_date: str, end_date: str, force_refresh: bool = False) -> pd.DatetimeIndex:
    """返回 [start_date, end_date] 区间内的 A 股交易日历。

    交易日历本地缓存一份全量历史，之后按需截取区间，避免每次都请求接口。
    交易日历数据本身极少变化，长期不用 force_refresh 也没问题。
    """
    if not force_refresh and _CALENDAR_CACHE_PATH.exists():
        calendar_df = pd.read_csv(_CALENDAR_CACHE_PATH)
    else:
        calendar_df = ak.tool_trade_date_hist_sina()
        DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        calendar_df.to_csv(_CALENDAR_CACHE_PATH, index=False)

    calendar_df["trade_date"] = pd.to_datetime(calendar_df["trade_date"])
    start_ts, end_ts = pd.Timestamp(start_date), pd.Timestamp(end_date)
    mask = (calendar_df["trade_date"] >= start_ts) & (calendar_df["trade_date"] <= end_ts)
    return pd.DatetimeIndex(sorted(calendar_df.loc[mask, "trade_date"]))
