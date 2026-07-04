"""对 daily_job.py 里 markdown 摘要生成逻辑的自测(不依赖真实网络)。

用法: python tests/test_daily_job.py
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daily_job import build_summary_markdown


def _signal_df(date, close, signal):
    return pd.DataFrame([{"date": pd.Timestamp(date), "close": close, "signal": signal}])


def test_summary_lists_triggered_signals_separately_from_hold_and_failed():
    results = {
        "600519": _signal_df("2026-07-03", 1194.45, "BUY"),
        "000858": _signal_df("2026-07-03", 120.5, "HOLD"),
        "601318": None,  # 模拟数据获取失败
    }
    summary = build_summary_markdown(results, as_of=datetime(2026, 7, 4))
    assert "2026-07-04" in summary

    triggered_section, _, rest = summary.partition("## 其余关注股票")
    hold_section, _, failed_section = rest.partition("## 数据获取失败")

    assert "600519" in triggered_section and "BUY" in triggered_section and "1194.45" in triggered_section
    assert "000858" in hold_section and "HOLD" in hold_section
    assert "601318" in failed_section
    print("test_summary_lists_triggered_signals_separately_from_hold_and_failed: PASS")


def test_summary_reports_no_signal_when_all_hold():
    results = {
        "600519": _signal_df("2026-07-03", 1194.45, "HOLD"),
        "000858": _signal_df("2026-07-03", 120.5, "HOLD"),
    }
    summary = build_summary_markdown(results, as_of=datetime(2026, 7, 4))
    assert "今天没有股票触发新的 BUY/SELL 信号" in summary
    print("test_summary_reports_no_signal_when_all_hold: PASS")


def test_summary_uses_most_recent_row_when_multiple_dates_present():
    df = pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-07-01"), "close": 100.0, "signal": "SELL"},
            {"date": pd.Timestamp("2026-07-03"), "close": 110.0, "signal": "BUY"},
        ]
    )
    summary = build_summary_markdown({"600519": df}, as_of=datetime(2026, 7, 4))
    assert "BUY" in summary and "110.00" in summary
    print("test_summary_uses_most_recent_row_when_multiple_dates_present: PASS")


def main():
    test_summary_lists_triggered_signals_separately_from_hold_and_failed()
    test_summary_reports_no_signal_when_all_hold()
    test_summary_uses_most_recent_row_when_multiple_dates_present()
    print("\n全部测试通过。")


if __name__ == "__main__":
    main()
