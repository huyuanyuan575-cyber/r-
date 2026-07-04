"""对比阶段5(纯策略信号)回测 vs 阶段6(叠加risk.rules风控规则)回测的最大回撤/年化收益差异。

网络在本沙箱环境不可用(同前几次)，用一段手工构造的多周期价格序列演示对比(价格亲民、
明确制造出金叉+放量、多轮涨跌循环，包含一次可以触发止盈的大涨和一段可以触发止损的
急跌)，而不是依赖随机游走的运气——重点是让"加风控前后"的差异有说服力、看得懂原因，
真实结论仍需用真实数据重新跑一遍(把这里手工构造的信号序列换成真实数据跑出来的
signal_df 即可，run_backtest/风控部分的调用方式完全不变)。
"""

import numpy as np
import pandas as pd

from backtest.engine import format_report, run_backtest
from risk.rules import RiskConfig
from strategies.ma_cross_rsi import generate_signals
from viz.plot_equity import plot_equity_curve

SYMBOL = "DEMO_MULTI_CYCLE"


def build_multi_cycle_signal_df(n: int = 400, base_price: float = 50.0) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=n)
    t = np.arange(n)
    closes = base_price + 0.02 * t + 12 * np.sin(2 * np.pi * t / 55)

    # 注入一段连续急跌(约18%)，用来对比"止损"能不能比"等死叉信号"更快止损
    crash_start = 250
    closes[crash_start : crash_start + 5] -= np.linspace(0, 9, 5)
    closes = np.maximum(closes, 5.0)

    def _with_volume(volumes):
        df = pd.DataFrame(
            {
                "date": dates,
                "close": closes,
                "open": closes,
                "high": closes * 1.005,
                "low": closes * 0.995,
                "volume": volumes,
                "amount": volumes * closes,
            }
        )
        df["pct_chg"] = df["close"].pct_change()
        df["ma5"] = df["close"].rolling(5, min_periods=5).mean()
        df["ma20"] = df["close"].rolling(20, min_periods=20).mean()
        df["rsi14"] = 50.0  # 固定值，本次演示只关心金叉/死叉+风控路径
        avg_vol5 = df["volume"].rolling(5, min_periods=5).mean().shift(1)
        df["volume_ratio5"] = df["volume"] / avg_vol5
        return df

    baseline_volume = np.full(n, 1_000_000.0)
    probe_df = _with_volume(baseline_volume)
    ma_diff = probe_df["ma5"] - probe_df["ma20"]
    golden_days = probe_df.index[(ma_diff > 0) & (ma_diff.shift(1) <= 0)]

    # 只在每次真正发生金叉的当天单独放量，确保 volume_ratio5 > 1.5 触发BUY
    volumes = baseline_volume.copy()
    volumes[golden_days] = baseline_volume[golden_days] * 5

    df = _with_volume(volumes)
    return generate_signals(df)


def main():
    signal_df = build_multi_cycle_signal_df()

    baseline = run_backtest(signal_df, SYMBOL, initial_capital=100_000, max_position_pct=0.2)
    risk_config = RiskConfig(
        max_position_pct=0.2,
        stop_loss_pct=0.08,
        take_profit_pct=0.30,
        take_profit_reduce_ratio=0.5,
        portfolio_drawdown_halt_pct=0.15,
    )
    with_risk = run_backtest(
        signal_df, SYMBOL, initial_capital=100_000, max_position_pct=0.2, risk_config=risk_config
    )

    print("=" * 60)
    print("阶段5：纯策略信号回测(无风控)")
    print("=" * 60)
    print(format_report(baseline, SYMBOL))

    print("\n" + "=" * 60)
    print("阶段6：叠加风控规则回测(止损8% + 止盈30%分批减半 + 组合回撤熔断15%)")
    print("=" * 60)
    print(format_report(with_risk, SYMBOL))

    print("\n" + "=" * 60)
    print("对比")
    print("=" * 60)
    bm, rm = baseline.metrics, with_risk.metrics
    print(f"最大回撤: 无风控 {bm['max_drawdown']:.2%}  vs  加风控 {rm['max_drawdown']:.2%}")
    print(f"年化收益率: 无风控 {bm['annualized_return']:.2%}  vs  加风控 {rm['annualized_return']:.2%}")
    print(f"交易次数: 无风控 {bm['num_trades']}  vs  加风控 {rm['num_trades']}")

    risk_trades = with_risk.trades_df()
    if not risk_trades.empty:
        print("\n加风控后的交易明细(含触发原因):")
        print(
            risk_trades[["entry_date", "exit_date", "shares", "pnl", "return_pct", "exit_reason"]].to_string(
                index=False
            )
        )

    plot_equity_curve(
        baseline.equity_curve, "viz/output/risk_compare_baseline_equity.png",
        metrics=baseline.metrics, title="No Risk Rules - Equity Curve",
    )
    plot_equity_curve(
        with_risk.equity_curve, "viz/output/risk_compare_with_risk_equity.png",
        metrics=with_risk.metrics, title="With Risk Rules - Equity Curve",
    )
    print(
        "\n净值曲线图已保存: viz/output/risk_compare_baseline_equity.png, "
        "viz/output/risk_compare_with_risk_equity.png"
    )


if __name__ == "__main__":
    main()
