"""对 strategies/ma_cross_rsi.py 的自测（不依赖 pytest，也不依赖真实网络）。

用法: python tests/test_strategies.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from strategies.ma_cross_rsi import generate_signals


def _make_factor_df(ma5, ma20, rsi14, volume_ratio5):
    n = len(ma5)
    return pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-02", periods=n),
            "ma5": ma5,
            "ma20": ma20,
            "rsi14": rsi14,
            "volume_ratio5": volume_ratio5,
        }
    )


def test_buy_signal_requires_golden_cross_and_volume():
    # day0: ma5<ma20(空仓状态); day1: 金叉且放量>1.5倍 -> BUY；
    # day2: 金叉但量能不足(1.2倍) -> 不应为BUY
    df = _make_factor_df(
        ma5=[10, 12, 15],
        ma20=[11, 11, 11],
        rsi14=[50, 50, 50],
        volume_ratio5=[1.0, 1.6, 1.2],
    )
    # 手动制造第2次"金叉"：把day1也变回死叉状态，day2再穿一次
    df.loc[1, ["ma5", "ma20"]] = [9, 11]  # day1 保持死叉(不是金叉)，不该触发BUY
    df.loc[2, ["ma5", "ma20"]] = [15, 11]  # day2 金叉，量比1.2 < 1.5，不该触发BUY

    result = generate_signals(df)
    assert result["signal"].iloc[1] != "BUY"
    assert result["signal"].iloc[2] != "BUY", "量比不足1.5倍时，即使金叉也不应买入"

    # 再补一天：金叉 + 放量2.0倍 -> 应为 BUY
    df2 = _make_factor_df(
        ma5=[9, 15],
        ma20=[11, 11],
        rsi14=[50, 50],
        volume_ratio5=[1.0, 2.0],
    )
    result2 = generate_signals(df2)
    assert result2["signal"].iloc[1] == "BUY", "金叉且放量2倍应触发BUY"
    print("test_buy_signal_requires_golden_cross_and_volume: PASS")


def test_sell_signal_on_death_cross_or_overbought():
    # day0: 金叉状态(ma5>ma20)，day1: 死叉 -> SELL
    df = _make_factor_df(
        ma5=[15, 9],
        ma20=[11, 11],
        rsi14=[50, 50],
        volume_ratio5=[1.0, 1.0],
    )
    result = generate_signals(df)
    assert result["signal"].iloc[1] == "SELL", "死叉应触发SELL"

    # RSI超买单独触发SELL，即使没有死叉
    df2 = _make_factor_df(
        ma5=[15, 16],
        ma20=[11, 11],
        rsi14=[50, 85],
        volume_ratio5=[1.0, 1.0],
    )
    result2 = generate_signals(df2)
    assert result2["signal"].iloc[1] == "SELL", "RSI>80应触发SELL，不需要死叉"
    print("test_sell_signal_on_death_cross_or_overbought: PASS")


def test_no_look_ahead_bias():
    """核心反作弊测试：截断到第t天算出的信号，必须和用完整数据算出的第t天信号完全一致。

    如果策略函数偷看了未来数据(比如用了 shift(-1)、centered rolling等)，截断后
    重新计算的信号会和完整数据算出的不一样，这个测试就会失败。
    """
    rng = np.random.default_rng(7)
    n = 80
    closes = 100 + np.cumsum(rng.normal(0, 1, size=n))
    ma5 = pd.Series(closes).rolling(5).mean()
    ma20 = pd.Series(closes).rolling(20).mean()
    rsi14 = pd.Series(rng.uniform(20, 95, size=n))
    volume_ratio5 = pd.Series(rng.uniform(0.5, 2.5, size=n))

    full_df = _make_factor_df(ma5, ma20, rsi14, volume_ratio5)
    full_result = generate_signals(full_df)

    for t in [25, 40, 60, n - 1]:
        truncated = full_df.iloc[: t + 1].reset_index(drop=True)
        truncated_result = generate_signals(truncated)
        assert truncated_result["signal"].iloc[t] == full_result["signal"].iloc[t], (
            f"第{t}天的信号在截断数据和完整数据下不一致，可能存在未来函数"
        )
    print("test_no_look_ahead_bias: PASS")


def test_insufficient_history_is_hold():
    df = _make_factor_df(
        ma5=[np.nan, 12],
        ma20=[np.nan, 11],
        rsi14=[np.nan, 50],
        volume_ratio5=[np.nan, 2.0],
    )
    result = generate_signals(df)
    assert result["signal"].iloc[0] == "HOLD", "指标历史不足(NaN)时应为HOLD"
    print("test_insufficient_history_is_hold: PASS")


def main():
    test_buy_signal_requires_golden_cross_and_volume()
    test_sell_signal_on_death_cross_or_overbought()
    test_no_look_ahead_bias()
    test_insufficient_history_is_hold()
    print("\n全部测试通过。")


if __name__ == "__main__":
    main()
