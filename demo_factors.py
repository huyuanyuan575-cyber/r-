"""演示 factors/technical.py：在清洗后的数据上叠加常用技术指标。

真实网络不可用时用 data.sample_data 构造一段较长的示例序列（保证 MA60 等长周期
指标有足够历史可算），跑一遍 清洗 -> 因子计算，打印结果确认逻辑正确。
"""

import pandas as pd

from data.cleaner import clean_daily_bars
from data.sample_data import build_sample_raw
from factors.technical import add_all_factors

SYMBOL = "600519"


def main():
    # 90个交易日、不注入停牌/异常，专注验证指标计算本身
    raw_df = build_sample_raw(
        SYMBOL, periods=90, suspension_indices=(), anomaly_index=None
    )
    calendar = pd.DatetimeIndex(pd.bdate_range(raw_df["date"].min(), raw_df["date"].max()))
    cleaned_df = clean_daily_bars(raw_df, symbol=SYMBOL, trade_calendar=calendar)

    factor_df = add_all_factors(cleaned_df)

    print("=" * 60)
    print(f"{SYMBOL} 因子计算结果（最后10行）")
    print("=" * 60)
    columns = [
        "date", "close",
        "ma5", "ma20", "ma60",
        "macd_dif", "macd_dea", "macd_hist",
        "rsi14",
        "boll_mid20", "boll_upper20", "boll_lower20",
        "momentum20", "volatility20", "volume_ratio5",
    ]
    print(factor_df[columns].tail(10).to_string(index=False))

    # 基本合理性检查：长周期指标在历史不足时应为 NaN，历史足够后应有值
    assert factor_df["ma60"].iloc[:59].isna().all(), "MA60 在前59行历史不足，应为 NaN"
    assert factor_df["ma60"].iloc[59:].notna().all(), "第60行起历史足够，MA60 应有值"
    assert factor_df["rsi14"].dropna().between(0, 100).all(), "RSI 应落在 [0, 100] 区间"
    print("\n断言通过：长周期指标在历史不足时为 NaN，RSI 落在合理区间。")


if __name__ == "__main__":
    main()
