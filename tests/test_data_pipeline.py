"""对 data/ 模块的抓取缓存与清洗逻辑做轻量自测（不依赖 pytest，也不依赖真实网络）。

用法: python tests/test_data_pipeline.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data.fetcher as fetcher_module
from data.cleaner import clean_daily_bars

CALL_LOG = []


def fake_stock_zh_a_hist(symbol, period, start_date, end_date, adjust):
    """用可预测的假数据模拟 akshare 接口，同时记录每次真实被调用的日期区间。"""
    CALL_LOG.append((start_date, end_date))
    dates = pd.bdate_range(start_date, end_date)
    return pd.DataFrame(
        {
            "日期": dates.strftime("%Y-%m-%d"),
            "股票代码": symbol,
            "开盘": 100.0,
            "收盘": 101.0,
            "最高": 102.0,
            "最低": 99.0,
            "成交量": 1_000_000,
            "成交额": 100_000_000,
        }
    )


def test_incremental_cache_only_fetches_missing_range():
    CALL_LOG.clear()
    symbol = "600519"

    df1 = fetcher_module.fetch_daily_bars(symbol, "20240101", "20240110", request_interval=0)
    assert len(CALL_LOG) == 1, f"首次拉取应发起1次接口请求，实际 {len(CALL_LOG)} 次"
    assert not df1.empty

    df2 = fetcher_module.fetch_daily_bars(symbol, "20240101", "20240110", request_interval=0)
    assert len(CALL_LOG) == 1, "重复请求同一区间不应再次调用接口（命中本地缓存）"
    assert len(df2) == len(df1)

    df3 = fetcher_module.fetch_daily_bars(symbol, "20240101", "20240120", request_interval=0)
    assert len(CALL_LOG) == 2, "扩展结束日期后应只发起1次增量请求，而不是重新拉取全部历史"
    fetched_start, fetched_end = CALL_LOG[1]
    assert fetched_start == "20240111", f"增量请求应从缓存最新日期之后开始，实际从 {fetched_start} 开始"

    assert df3["date"].is_monotonic_increasing
    assert df3["date"].duplicated().sum() == 0, "合并缓存与新数据后不应出现重复日期"

    print("test_incremental_cache_only_fetches_missing_range: PASS")


def test_clean_daily_bars_marks_suspension_and_anomaly():
    symbol = "600519"
    dates = pd.date_range("2024-01-02", periods=10, freq="B").delete([4])  # 抽掉1天模拟停牌
    closes = np.array([100, 101, 102, 103, 130, 104, 105, 106, 107], dtype=float)
    raw = pd.DataFrame(
        {
            "date": dates,
            "symbol": symbol,
            "open": closes,
            "high": closes + 1,
            "low": closes - 1,
            "close": closes,
            "volume": 1_000_000,
            "amount": 100_000_000,
        }
    )

    calendar = pd.DatetimeIndex(pd.bdate_range(dates.min(), dates.max()))
    cleaned = clean_daily_bars(raw, symbol=symbol, trade_calendar=calendar)

    assert cleaned["is_suspended"].sum() == 1, "应识别出1个停牌交易日"
    suspended_row = cleaned[cleaned["is_suspended"]].iloc[0]
    assert suspended_row[["open", "high", "low", "close", "volume", "amount"]].isna().all(), (
        "停牌日应为 NaN，而不是 0"
    )
    assert cleaned["is_price_anomaly"].sum() >= 1, "应识别出至少1条异常涨跌幅"

    print("test_clean_daily_bars_marks_suspension_and_anomaly: PASS")


def main():
    tmp_dir = tempfile.mkdtemp(prefix="data_pipeline_test_")
    original_dir = fetcher_module.DATA_RAW_DIR
    original_hist = fetcher_module.ak.stock_zh_a_hist
    try:
        fetcher_module.DATA_RAW_DIR = Path(tmp_dir)
        fetcher_module.ak.stock_zh_a_hist = fake_stock_zh_a_hist

        test_incremental_cache_only_fetches_missing_range()
        test_clean_daily_bars_marks_suspension_and_anomaly()
    finally:
        fetcher_module.DATA_RAW_DIR = original_dir
        fetcher_module.ak.stock_zh_a_hist = original_hist
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("\n全部测试通过。")


if __name__ == "__main__":
    main()
