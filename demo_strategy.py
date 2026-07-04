"""演示 strategies/ma_cross_rsi.py：MA5/MA20金叉死叉 + 量能确认 + RSI超买策略。

1. 先尝试真实拉取贵州茅台(600519)最近一年的日线数据。
2. 若网络不可用，回退到 data.sample_data 构造的示例序列，仅用于验证流程和画图效果，
   不代表真实行情——真实的买卖点判断必须用真实数据重新跑一遍。
3. 清洗 -> 计算全部技术指标 -> 生成买卖信号 -> 打印信号日期列表 -> 画图标注买卖点。
"""

from datetime import datetime, timedelta

import pandas as pd

from data.cleaner import clean_daily_bars
from data.fetcher import fetch_daily_bars
from data.sample_data import build_sample_raw
from factors.technical import add_all_factors
from strategies.ma_cross_rsi import generate_signals
from viz.plot_signals import plot_price_with_signals

SYMBOL = "600519"
OUT_PATH = "viz/output/600519_signals.png"


def load_data():
    end = datetime.now()
    start = end - timedelta(days=365)
    try:
        raw_df = fetch_daily_bars(SYMBOL, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        if raw_df.empty:
            raise RuntimeError("接口返回空数据")
        print(f"真实数据获取成功：{len(raw_df)} 条")
        from data.calendar import get_trade_calendar

        calendar = get_trade_calendar(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        return raw_df, calendar, True
    except Exception as exc:
        print(f"真实数据获取失败（{exc}），改用示例数据演示流程（不代表真实行情）")
        raw_df = build_sample_raw(
            SYMBOL, periods=250, suspension_indices=(), anomaly_index=None
        )
        return raw_df, None, False


def main():
    raw_df, calendar, is_real = load_data()

    cleaned_df = clean_daily_bars(raw_df, symbol=SYMBOL, trade_calendar=calendar)
    factor_df = add_all_factors(cleaned_df)
    signal_df = generate_signals(factor_df)

    trades = signal_df[signal_df["signal"] != "HOLD"][["date", "close", "signal"]]
    print("\n" + "=" * 60)
    print(f"过去一年 {SYMBOL} 的买卖点信号（{'真实数据' if is_real else '示例数据，仅演示流程'}）")
    print("=" * 60)
    if trades.empty:
        print("(无信号触发)")
    else:
        print(trades.to_string(index=False))

    out_path = plot_price_with_signals(
        signal_df, SYMBOL, OUT_PATH, title=f"{SYMBOL} Price & BUY/SELL Signals"
    )
    print(f"\n图表已保存: {out_path}")


if __name__ == "__main__":
    main()
