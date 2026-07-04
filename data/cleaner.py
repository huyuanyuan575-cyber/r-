"""日线数据清洗：停牌日标记为 NaN、涨跌幅超出理论涨跌停限制的异常值标记。"""

import numpy as np
import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume", "amount"]


def price_limit_pct(symbol: str) -> float:
    """A股涨跌停幅度的粗略规则。

    注意：ST/*ST 股票涨跌停为 5%，但本项目当前数据源未附带 ST 状态，
    这里无法区分，统一按主板 10% 计算——ST 股票可能因此被漏判部分正常
    涨跌停（不会被误判为异常，只是判定阈值偏宽）。
    """
    if symbol.startswith(("300", "301", "688", "689")):
        return 0.20  # 创业板 / 科创板
    if symbol.startswith(("8", "4")):
        return 0.30  # 北交所，规则较特殊，此处仅粗略处理
    return 0.10  # 主板 / 中小板


def clean_daily_bars(
    df: pd.DataFrame,
    symbol: str,
    trade_calendar: pd.DatetimeIndex | None = None,
    anomaly_tolerance: float = 0.02,
) -> pd.DataFrame:
    """清洗单只股票的日线数据。

    - 若提供 trade_calendar：按标准交易日历重建索引，缺失的交易日（停牌）
      整行行情字段标记为 NaN，而不是 0 填充，也不是被静默丢弃。
    - 涨跌幅超过该股票理论涨跌停限制(+容差)的数据行标记 is_price_anomaly=True，
      供人工复核，不自动删除或修改。
    """
    df = df.sort_values("date").drop_duplicates(subset="date").reset_index(drop=True)

    if trade_calendar is not None and len(df) > 0:
        full_index = trade_calendar[
            (trade_calendar >= df["date"].min()) & (trade_calendar <= df["date"].max())
        ]
        df = df.set_index("date").reindex(full_index)
        df.index.name = "date"
        df = df.reset_index()
        df["symbol"] = symbol

    df["is_suspended"] = df["volume"].isna() | (df["volume"] == 0)
    # 停牌日不做 0 填充，价格/成交量字段显式置为 NaN
    df.loc[df["is_suspended"], OHLCV_COLUMNS] = np.nan

    df["pct_chg"] = df["close"].pct_change()

    limit = price_limit_pct(symbol)
    df["is_price_anomaly"] = df["pct_chg"].abs() > (limit + anomaly_tolerance)
    # 停牌前后缺少可比较的前一日收盘价，无法判断涨跌幅，不计入异常
    df.loc[df["pct_chg"].isna(), "is_price_anomaly"] = False

    return df
