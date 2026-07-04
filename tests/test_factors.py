"""对 factors/technical.py 的自测（不依赖 pytest，也不依赖真实网络）。

用法: python tests/test_factors.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factors.technical import bollinger_bands, macd, moving_average, rsi


def _make_close_df(closes):
    dates = pd.bdate_range("2024-01-02", periods=len(closes))
    return pd.DataFrame({"date": dates, "close": closes})


def test_moving_average_matches_manual_calc():
    closes = [10, 11, 12, 13, 14, 15]
    df = moving_average(_make_close_df(closes), windows=(3,))
    # 前2行历史不足3天，应为 NaN；第3行起 = 最近3天均值
    assert df["ma3"].iloc[:2].isna().all()
    expected = [(10 + 11 + 12) / 3, (11 + 12 + 13) / 3, (12 + 13 + 14) / 3, (13 + 14 + 15) / 3]
    np.testing.assert_allclose(df["ma3"].iloc[2:].to_numpy(), expected)
    print("test_moving_average_matches_manual_calc: PASS")


def test_rsi_all_gains_is_100():
    # 连续上涨、无下跌，RSI 应为100（避免除零产生 NaN/inf）
    closes = list(range(100, 130))
    df = rsi(_make_close_df(closes), window=14)
    assert (df["rsi14"].dropna() == 100).all(), "连续上涨时 RSI 应恒为100"
    print("test_rsi_all_gains_is_100: PASS")


def test_bollinger_bands_ordering():
    rng = np.random.default_rng(0)
    closes = 100 + np.cumsum(rng.normal(0, 1, size=40))
    df = bollinger_bands(_make_close_df(closes), window=20, num_std=2.0)
    valid = df.dropna(subset=["boll_upper20", "boll_lower20"])
    assert (valid["boll_upper20"] >= valid["boll_mid20"]).all()
    assert (valid["boll_mid20"] >= valid["boll_lower20"]).all()
    print("test_bollinger_bands_ordering: PASS")


def test_macd_hist_equals_twice_dif_minus_dea():
    rng = np.random.default_rng(1)
    closes = 100 + np.cumsum(rng.normal(0, 1, size=60))
    df = macd(_make_close_df(closes))
    valid = df.dropna(subset=["macd_hist"])
    np.testing.assert_allclose(
        valid["macd_hist"].to_numpy(), 2 * (valid["macd_dif"] - valid["macd_dea"]).to_numpy()
    )
    print("test_macd_hist_equals_twice_dif_minus_dea: PASS")


def main():
    test_moving_average_matches_manual_calc()
    test_rsi_all_gains_is_100()
    test_bollinger_bands_ordering()
    test_macd_hist_equals_twice_dif_minus_dea()
    print("\n全部测试通过。")


if __name__ == "__main__":
    main()
