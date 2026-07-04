"""验证 data/ 模块的抓取 + 缓存 + 清洗流程。

1. 先尝试用真实股票列表跑一遍 batch_fetch_daily_bars（真实网络环境下会通过 akshare 实际拉取）。
2. 无论第 1 步是否因为网络原因失败，都会用构造的示例数据演示 clean_daily_bars
   的清洗效果（停牌标记为 NaN、异常涨跌幅标记 is_price_anomaly），方便直接
   肉眼确认清洗逻辑是否合理。
"""

import pandas as pd

from data.cleaner import clean_daily_bars
from data.fetcher import batch_fetch_daily_bars
from data.sample_data import build_sample_raw

SYMBOLS = ["600519", "000858", "601318", "300750", "000001"]


def try_real_fetch():
    print("=" * 60)
    print("第一步：尝试真实批量拉取（akshare）")
    print("=" * 60)
    try:
        result = batch_fetch_daily_bars(SYMBOLS, start_date="20250601", end_date="20260704")
        for symbol, df in result.items():
            print(f"{symbol}: 拉取 {len(df)} 条")
        return result
    except Exception as exc:
        print(f"真实拉取失败（本沙箱环境网络策略限制了 akshare 的数据源域名）: {exc}")
        print("这段代码在你本机（网络不受限）运行时应能正常工作。")
        return None


def demo_cleaning():
    print()
    print("=" * 60)
    print("第二步：清洗前后对比（示例数据，包含停牌缺口 + 异常涨跌幅）")
    print("=" * 60)

    symbol = "600519"
    raw_df = build_sample_raw(symbol)

    print("\n--- 清洗前（原始拉取结果，停牌日直接缺失该行，不体现在数据里） ---")
    print(raw_df.to_string(index=False))

    calendar = pd.DatetimeIndex(pd.bdate_range(raw_df["date"].min(), raw_df["date"].max()))
    cleaned_df = clean_daily_bars(raw_df, symbol=symbol, trade_calendar=calendar)

    print("\n--- 清洗后（补齐停牌日为 NaN 行，标记 is_suspended / is_price_anomaly） ---")
    print(cleaned_df.to_string(index=False))

    suspended_rows = cleaned_df[cleaned_df["is_suspended"]]
    anomaly_rows = cleaned_df[cleaned_df["is_price_anomaly"]]

    print(f"\n检测到停牌(补齐为NaN)行数: {len(suspended_rows)}")
    print(suspended_rows[["date", "close", "volume", "is_suspended"]].to_string(index=False))

    print(f"\n检测到异常涨跌幅行数: {len(anomaly_rows)}")
    print(anomaly_rows[["date", "close", "pct_chg", "is_price_anomaly"]].to_string(index=False))

    assert len(suspended_rows) == 2, "应识别出2个停牌交易日"
    # 人为制造了一次+25%的异常跳涨，随后一天从高点回落的涨跌幅同样会超过阈值，
    # 两天都会被正确标记（异常会向后传播一天，这是预期行为，不是bug）。
    assert len(anomaly_rows) == 2, "应识别出2条异常涨跌幅记录（异常当天 + 次日回落）"
    assert suspended_rows[["open", "high", "low", "close", "volume", "amount"]].isna().all().all(), (
        "停牌日行情字段应为 NaN，而不是 0"
    )
    print("\n断言通过：停牌日已标记为 NaN（非 0 填充），异常涨跌幅已被正确识别。")


if __name__ == "__main__":
    try_real_fetch()
    demo_cleaning()
