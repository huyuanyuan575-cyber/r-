"""对 strategies/multi_factor_score.py 的自测（不依赖 pytest，也不依赖真实网络）。

用法: python tests/test_multi_factor_score.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from strategies.multi_factor_score import _industry_zscore, _zscore, score_stocks


def test_zscore_matches_manual_calc():
    series = pd.Series([10.0, 20.0, 30.0, 40.0])
    result = _zscore(series)
    mean, std = series.mean(), series.std()
    expected = (series - mean) / std
    np.testing.assert_allclose(result.to_numpy(), expected.to_numpy())
    print("test_zscore_matches_manual_calc: PASS")


def test_zscore_constant_series_is_zero():
    # 标准差为0(全部相同)时，不该产生 inf/NaN，应记为中性0
    series = pd.Series([5.0, 5.0, 5.0])
    result = _zscore(series)
    assert (result == 0).all()
    print("test_zscore_constant_series_is_zero: PASS")


def test_industry_zscore_singleton_group_is_zero():
    # X行业有2只股票可以相对比较，Y/Z行业各只有1只股票，无从比较，应记为中性0
    values = pd.Series([-10.0, -30.0, -5.0, -50.0])  # 即 -PE
    industry = pd.Series(["X", "X", "Y", "Z"])
    result = _industry_zscore(values, industry)

    x_mean, x_std = pd.Series([-10.0, -30.0]).mean(), pd.Series([-10.0, -30.0]).std()
    assert np.isclose(result.iloc[0], (-10.0 - x_mean) / x_std)
    assert np.isclose(result.iloc[1], (-30.0 - x_mean) / x_std)
    assert result.iloc[2] == 0, "行业内只有1只股票时，估值因子应记为中性0"
    assert result.iloc[3] == 0, "行业内只有1只股票时，估值因子应记为中性0"
    print("test_industry_zscore_singleton_group_is_zero: PASS")


def _make_fake_ohlcv(base_price: float, daily_drift: float, daily_vol: float, seed: int):
    """构造一段有确定趋势(daily_drift)和噪声水平(daily_vol)的示例价格序列，
    用于制造出动量、波动率因子上有明显差异、排名理由说得清楚的测试数据。"""
    rng = np.random.default_rng(seed)
    n = 120
    dates = pd.bdate_range("2023-08-01", periods=n)
    daily_returns = daily_drift + rng.normal(0, daily_vol, size=n)
    closes = base_price * np.cumprod(1 + daily_returns)
    return pd.DataFrame(
        {
            "date": dates,
            "symbol": "TEST",
            "open": closes,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": 1_000_000,
            "amount": 100_000_000,
        }
    )


def test_score_stocks_ranks_by_composite_and_explains_direction():
    symbols = ["HIGH_ALL", "LOW_PE_ONLY", "LOSER"]
    as_of_date = "2023-12-29"

    fundamentals_by_symbol = {
        "HIGH_ALL": {"industry": "IND1", "pe": 15.0},   # 同行业内PE较低 -> 估值因子应占优
        "LOW_PE_ONLY": {"industry": "IND1", "pe": 35.0},  # 同行业内PE较高 -> 估值因子应落后
        "LOSER": {"industry": "IND2", "pe": 20.0},        # 单独行业，估值因子记0(中性)
    }

    def fake_fundamentals_provider(syms, date):
        return pd.DataFrame(
            [{"symbol": s, **fundamentals_by_symbol[s]} for s in syms]
        )

    fake_ohlcv_by_symbol = {
        # 强势上涨、低波动 -> 动量因子和波动率因子都应占优
        "HIGH_ALL": _make_fake_ohlcv(base_price=100, daily_drift=0.004, daily_vol=0.005, seed=1),
        # 小幅上涨、低波动
        "LOW_PE_ONLY": _make_fake_ohlcv(base_price=100, daily_drift=0.001, daily_vol=0.005, seed=2),
        # 下跌、高波动 -> 动量和波动率因子都应垫底
        "LOSER": _make_fake_ohlcv(base_price=100, daily_drift=-0.004, daily_vol=0.02, seed=3),
    }

    def fake_ohlcv_provider(symbol, date):
        return fake_ohlcv_by_symbol[symbol]

    result = score_stocks(
        symbols,
        as_of_date,
        ohlcv_provider=fake_ohlcv_provider,
        fundamentals_provider=fake_fundamentals_provider,
    )

    # HIGH_ALL 三个因子都占优，理应综合得分最高、排名第一
    assert result.loc[result["symbol"] == "HIGH_ALL", "rank"].iloc[0] == 1
    # LOSER 动量和波动率都垫底，理应综合得分最低、排名最后
    assert result.loc[result["symbol"] == "LOSER", "rank"].iloc[0] == len(symbols)

    high_all = result[result["symbol"] == "HIGH_ALL"].iloc[0]
    loser = result[result["symbol"] == "LOSER"].iloc[0]
    assert high_all["momentum_zscore"] > loser["momentum_zscore"]
    assert high_all["volatility_zscore"] > loser["volatility_zscore"]
    assert high_all["valuation_zscore"] > 0, "同行业内PE更低，估值因子应为正"
    assert result.loc[result["symbol"] == "LOW_PE_ONLY", "valuation_zscore"].iloc[0] < 0, (
        "同行业内PE更高，估值因子应为负"
    )

    print("test_score_stocks_ranks_by_composite_and_explains_direction: PASS")


def main():
    test_zscore_matches_manual_calc()
    test_zscore_constant_series_is_zero()
    test_industry_zscore_singleton_group_is_zero()
    test_score_stocks_ranks_by_composite_and_explains_direction()
    print("\n全部测试通过。")


if __name__ == "__main__":
    main()
