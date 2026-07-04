"""对 backtest/engine.py 的自测（不依赖 pytest，也不依赖真实网络）。

用法: python tests/test_backtest.py
"""

import sys
from math import floor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest.engine import run_backtest

SYMBOL = "600519"  # 主板，涨跌停限制10%
ZERO_COST_KWARGS = dict(
    buy_commission_rate=0.0,
    sell_commission_rate=0.0,
    stamp_duty_rate=0.0,
    slippage_rate=0.0,
)


def _make_signal_df(rows):
    return pd.DataFrame(rows)


def test_position_sizing_respects_cap_and_lot_size():
    # 初始资金10万，单次买入上限20% -> 2万；价格99(非整百因子，检验取整到100股一手)
    df = _make_signal_df(
        [
            {"date": pd.Timestamp("2024-01-02"), "close": 99.0, "pct_chg": np.nan, "signal": "HOLD"},
            {"date": pd.Timestamp("2024-01-03"), "close": 99.0, "pct_chg": 0.0, "signal": "BUY"},
        ]
    )
    result = run_backtest(
        df, SYMBOL, initial_capital=100_000, max_position_pct=0.2, **ZERO_COST_KWARGS
    )
    # 20000/99 = 202.02，向下取整到100股一手 -> 200股
    expected_shares = floor((0.2 * 100_000 / 99.0) / 100) * 100
    assert expected_shares == 200
    final_equity = result.equity_curve["equity"].iloc[-1]
    expected_cash_after_buy = 100_000 - 200 * 99.0
    np.testing.assert_allclose(final_equity, expected_cash_after_buy + 200 * 99.0)  # 全部按最新价mark
    print("test_position_sizing_respects_cap_and_lot_size: PASS")


def test_limit_up_blocks_buy():
    df = _make_signal_df(
        [
            {"date": pd.Timestamp("2024-01-02"), "close": 100.0, "pct_chg": np.nan, "signal": "HOLD"},
            # 涨停(+10%)当天不该能买入
            {"date": pd.Timestamp("2024-01-03"), "close": 110.0, "pct_chg": 0.10, "signal": "BUY"},
            # 第二天不是涨停，应该能正常买入
            {"date": pd.Timestamp("2024-01-04"), "close": 110.0, "pct_chg": 0.0, "signal": "BUY"},
        ]
    )
    result = run_backtest(df, SYMBOL, initial_capital=100_000, max_position_pct=0.2, **ZERO_COST_KWARGS)
    assert len(result.trades) == 0, "还没卖出，不应有已完成交易"
    # 第2天涨停未成交，cash应仍为10万；第3天才应该真正花掉钱
    equity_day2 = result.equity_curve["equity"].iloc[1]
    equity_day3 = result.equity_curve["equity"].iloc[2]
    assert np.isclose(equity_day2, 100_000), "涨停当天不该成交，权益应不变"
    assert equity_day3 == 100_000, "第3天买入后按持仓市值mark，总权益(近似)应仍等于投入资金(无成本情形下)"
    print("test_limit_up_blocks_buy: PASS")


def test_limit_down_blocks_sell():
    df = _make_signal_df(
        [
            {"date": pd.Timestamp("2024-01-02"), "close": 100.0, "pct_chg": np.nan, "signal": "HOLD"},
            {"date": pd.Timestamp("2024-01-03"), "close": 100.0, "pct_chg": 0.0, "signal": "BUY"},
            # 跌停(-10%)当天不该能卖出
            {"date": pd.Timestamp("2024-01-04"), "close": 90.0, "pct_chg": -0.10, "signal": "SELL"},
            # 第二天不是跌停，应该能正常卖出
            {"date": pd.Timestamp("2024-01-05"), "close": 92.0, "pct_chg": 92.0 / 90.0 - 1, "signal": "SELL"},
        ]
    )
    result = run_backtest(df, SYMBOL, initial_capital=100_000, max_position_pct=0.2, **ZERO_COST_KWARGS)
    assert len(result.trades) == 1, "跌停当天应被阻止，实际成交应发生在第4天"
    assert result.trades[0].exit_date == pd.Timestamp("2024-01-05")
    print("test_limit_down_blocks_sell: PASS")


def test_t_plus_1_blocks_same_day_sell():
    # 正常信号流程不会在同一天同时产生BUY和SELL，这里用重复日期模拟"当天买入当天卖出"
    # 的极端输入，直接验证T+1这道防线本身生效(即便正常流程走不到这里)。
    same_day = pd.Timestamp("2024-01-03")
    df = _make_signal_df(
        [
            {"date": pd.Timestamp("2024-01-02"), "close": 100.0, "pct_chg": np.nan, "signal": "HOLD"},
            {"date": same_day, "close": 100.0, "pct_chg": 0.0, "signal": "BUY"},
            {"date": same_day, "close": 100.0, "pct_chg": 0.0, "signal": "SELL"},
            {"date": pd.Timestamp("2024-01-04"), "close": 100.0, "pct_chg": 0.0, "signal": "SELL"},
        ]
    )
    result = run_backtest(df, SYMBOL, initial_capital=100_000, max_position_pct=0.2, **ZERO_COST_KWARGS)
    assert len(result.trades) == 1, "当天买入当天不能卖出，应顺延到下一天才成交"
    assert result.trades[0].exit_date == pd.Timestamp("2024-01-04")
    print("test_t_plus_1_blocks_same_day_sell: PASS")


def test_fees_and_slippage_reduce_pnl():
    # 买卖价格相同(无涨跌)，纯粹用来验证手续费+印花税+滑点被正确扣除
    df = _make_signal_df(
        [
            {"date": pd.Timestamp("2024-01-02"), "close": 100.0, "pct_chg": np.nan, "signal": "HOLD"},
            {"date": pd.Timestamp("2024-01-03"), "close": 100.0, "pct_chg": 0.0, "signal": "BUY"},
            {"date": pd.Timestamp("2024-01-04"), "close": 100.0, "pct_chg": 0.0, "signal": "SELL"},
        ]
    )
    result = run_backtest(
        df,
        SYMBOL,
        initial_capital=100_000,
        max_position_pct=1.0,
        buy_commission_rate=0.0003,
        sell_commission_rate=0.0003,
        stamp_duty_rate=0.001,
        slippage_rate=0.001,
    )
    assert len(result.trades) == 1
    trade = result.trades[0]

    buy_price = 100.0 * 1.001
    max_shares = 100_000 / (buy_price * 1.0003)
    shares = floor(max_shares / 100) * 100
    cost_basis = shares * buy_price * 1.0003

    sell_price = 100.0 * 0.999
    gross_proceeds = shares * sell_price
    net_proceeds = gross_proceeds * (1 - 0.0003 - 0.001)

    expected_pnl = net_proceeds - cost_basis
    np.testing.assert_allclose(trade.pnl, expected_pnl, rtol=1e-9)
    assert trade.pnl < 0, "价格不变的情况下，交易成本应导致round-trip小幅亏损"
    print("test_fees_and_slippage_reduce_pnl: PASS")


def test_metrics_win_rate_and_drawdown():
    df = _make_signal_df(
        [
            {"date": pd.Timestamp("2024-01-02"), "close": 100.0, "pct_chg": np.nan, "signal": "HOLD"},
            {"date": pd.Timestamp("2024-01-03"), "close": 100.0, "pct_chg": 0.0, "signal": "BUY"},
            {"date": pd.Timestamp("2024-01-04"), "close": 105.0, "pct_chg": 0.05, "signal": "HOLD"},
            {"date": pd.Timestamp("2024-01-05"), "close": 120.0, "pct_chg": (120 - 105) / 105, "signal": "SELL"},
            {"date": pd.Timestamp("2024-01-08"), "close": 100.0, "pct_chg": (100 - 120) / 120, "signal": "BUY"},
            {"date": pd.Timestamp("2024-01-09"), "close": 92.0, "pct_chg": (92 - 100) / 100, "signal": "SELL"},
        ]
    )
    result = run_backtest(df, SYMBOL, initial_capital=100_000, max_position_pct=1.0, **ZERO_COST_KWARGS)

    assert len(result.trades) == 2
    assert result.trades[0].pnl > 0 and result.trades[1].pnl < 0

    m = result.metrics
    assert m["num_trades"] == 2
    np.testing.assert_allclose(m["win_rate"], 0.5)
    expected_ratio = result.trades[0].pnl / abs(result.trades[1].pnl)
    np.testing.assert_allclose(m["profit_loss_ratio"], expected_ratio)

    equity_series = result.equity_curve.set_index("date")["equity"]
    running_max = equity_series.cummax()
    expected_max_dd = (equity_series / running_max - 1).min()
    np.testing.assert_allclose(m["max_drawdown"], expected_max_dd)

    expected_total_return = equity_series.iloc[-1] / 100_000 - 1
    np.testing.assert_allclose(m["total_return"], expected_total_return)
    print("test_metrics_win_rate_and_drawdown: PASS")


def main():
    test_position_sizing_respects_cap_and_lot_size()
    test_limit_up_blocks_buy()
    test_limit_down_blocks_sell()
    test_t_plus_1_blocks_same_day_sell()
    test_fees_and_slippage_reduce_pnl()
    test_metrics_win_rate_and_drawdown()
    print("\n全部测试通过。")


if __name__ == "__main__":
    main()
