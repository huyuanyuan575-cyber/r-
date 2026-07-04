"""构造示例日线数据，供本沙箱环境无法连通真实数据源时演示 data/factors 各模块用。

真实使用时应改用 data.fetcher.batch_fetch_daily_bars 拉取的真实数据；这里的随机游走
数据仅用于验证清洗/因子计算逻辑本身是否正确，不代表任何真实行情。
"""

import numpy as np
import pandas as pd

from data.fetcher import STANDARD_COLUMNS


def build_sample_raw(
    symbol: str,
    periods: int = 20,
    start: str = "2024-01-02",
    seed: int = 42,
    suspension_indices=(7, 8),
    anomaly_index: int | None = 10,
    base_price: float = 1700.0,
) -> pd.DataFrame:
    """构造一段随机游走的示例原始日线数据。

    suspension_indices: 在生成的连续交易日序列中抽掉这些位置，模拟停牌缺口。
    anomaly_index: 在抽掉停牌日之后的序列里，对该位置人为制造一次超涨跌停的跳变；
        传 None 则不注入异常。
    """
    dates = pd.date_range(start, periods=periods, freq="B")
    if suspension_indices:
        dates = dates.delete(list(suspension_indices))

    rng = np.random.default_rng(seed=seed)
    closes = base_price + np.cumsum(rng.normal(0, 5, size=len(dates)))

    df = pd.DataFrame(
        {
            "date": dates,
            "symbol": symbol,
            "open": closes - 2,
            "high": closes + 5,
            "low": closes - 5,
            "close": closes,
            "volume": rng.integers(1_000_000, 5_000_000, size=len(dates)),
            "amount": rng.integers(1_000_000_000, 5_000_000_000, size=len(dates)),
        }
    )

    if anomaly_index is not None:
        # 人为制造一次异常涨跌幅（例如疑似复权错误/数据错误）：主板股票单日涨跌不该超过10%
        df.loc[anomaly_index, "close"] = df.loc[anomaly_index - 1, "close"] * 1.25
        df.loc[anomaly_index, "high"] = df.loc[anomaly_index, "close"] + 5
        df.loc[anomaly_index, "open"] = df.loc[anomaly_index - 1, "close"] * 1.02

    return df[STANDARD_COLUMNS]
