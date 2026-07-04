"""演示 backtest/engine.py：用阶段4a的MA金叉死叉+RSI策略，在贵州茅台近2年数据上回测。

1. 先尝试真实拉取贵州茅台(600519)近2年日线数据。
2. 网络不可用时回退到示例数据（仅演示流程，不代表真实行情，真实结论必须用真实数据重跑）。
3. 清洗 -> 计算指标 -> 生成信号 -> 回测(手续费+印花税+滑点+T+1+涨跌停+仓位限制) -> 输出报告与净值曲线图。
"""

from datetime import datetime, timedelta

from backtest.engine import format_report, run_backtest
from data.cleaner import clean_daily_bars
from data.fetcher import fetch_daily_bars
from data.sample_data import build_sample_raw
from factors.technical import add_all_factors
from strategies.ma_cross_rsi import generate_signals
from viz.plot_equity import plot_equity_curve

SYMBOL = "600519"
OUT_PATH = "viz/output/600519_backtest_equity.png"


def load_data():
    end = datetime.now()
    start = end - timedelta(days=365 * 2)
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
        raw_df = build_sample_raw(SYMBOL, periods=500, suspension_indices=(), anomaly_index=None)
        return raw_df, None, False


def _print_result(result, label):
    print("\n" + "=" * 60)
    print(f"过去2年 {SYMBOL} 回测报告（{label}）")
    print("=" * 60)
    print(format_report(result, SYMBOL))

    trades_df = result.trades_df()
    print(f"\n共 {len(trades_df)} 笔已平仓交易：")
    if not trades_df.empty:
        print(
            trades_df[["entry_date", "entry_price", "exit_date", "exit_price", "pnl", "return_pct"]].to_string(
                index=False
            )
        )


def main():
    raw_df, calendar, is_real = load_data()

    cleaned_df = clean_daily_bars(raw_df, symbol=SYMBOL, trade_calendar=calendar)
    factor_df = add_all_factors(cleaned_df)
    signal_df = generate_signals(factor_df)

    result = run_backtest(signal_df, SYMBOL, initial_capital=100_000, max_position_pct=0.2)
    _print_result(result, "真实数据" if is_real else "示例数据，价格贴近茅台真实价位(约1700元/股)，仅演示流程")

    if result.metrics["num_trades"] == 0:
        # 茅台股价高(示例数据基准价约1700元/股，与截图里的真实价位量级一致)，A股100股一手：
        # 买1手至少要 100 * 股价 ≈ 17万，而 20% 仓位上限 = 10万 * 20% = 2万，连1手都买不起。
        # 这不是策略没触发信号，是"高价股 + 100手 + 20%仓位上限 + 10万本金"这个组合本身就
        # 结构性地几乎不可能成交——用真实数据回测大概率也会遇到同样的问题，值得直接告诉用户，
        # 而不是把"0笔交易"误报成"策略没有效果"。
        print(
            "\n[重要提示] 0笔交易的原因不是策略没有信号，而是仓位约束太紧：\n"
            f"  20%仓位上限 = 10万 x 20% = 2万元，而按约1700元/股、100股一手计算，\n"
            f"  买1手至少要 17万元，超过账户全部本金。真实茅台数据大概率会遇到同样问题，\n"
            "  如果想让这个策略在茅台这类高价股上真正跑起来，需要调大初始资金或放宽仓位上限。"
        )

    out_path = plot_equity_curve(
        result.equity_curve, OUT_PATH, metrics=result.metrics, title=f"{SYMBOL} Backtest Equity Curve"
    )
    print(f"\n净值曲线图已保存: {out_path}")

    if result.metrics["num_trades"] == 0:
        # 引擎自检：手工构造一段价格亲民(50元附近)、明确有金叉+放量+死叉的信号序列
        # (不依赖随机游走的运气)，证明费用/滑点/T+1/涨跌停/净值曲线/报告这套机制本身是
        # 通的，问题只出在上面那个"茅台价格 x 100股一手 x 20%仓位上限"的资金约束上，
        # 不是回测引擎有bug。
        cheap_symbol = "TEST_CHEAP"
        cheap_signal = _build_guaranteed_round_trip_signal_df()
        cheap_result = run_backtest(cheap_signal, cheap_symbol, initial_capital=100_000, max_position_pct=0.2)
        print("\n" + "=" * 60)
        print("[引擎自检] 手工构造的价格亲民(约50元/股)示例信号序列，验证回测机制可以正常成交")
        print("=" * 60)
        print(format_report(cheap_result, cheap_symbol))
        cheap_trades = cheap_result.trades_df()
        if not cheap_trades.empty:
            print(f"\n共 {len(cheap_trades)} 笔已平仓交易：")
            print(
                cheap_trades[["entry_date", "entry_price", "exit_date", "exit_price", "pnl", "return_pct"]].to_string(
                    index=False
                )
            )
        cheap_out_path = "viz/output/engine_selfcheck_equity.png"
        plot_equity_curve(
            cheap_result.equity_curve, cheap_out_path, metrics=cheap_result.metrics,
            title="Engine Self-Check Equity Curve (cheap illustrative stock)",
        )
        print(f"\n引擎自检净值曲线图已保存: {cheap_out_path}")


def _build_guaranteed_round_trip_signal_df():
    """手工构造一段确定会触发 BUY 和 SELL 的信号序列，用于回测引擎自检
    (不依赖策略信号生成，策略本身的正确性已经在 tests/test_strategies.py 里验证过)。"""
    import numpy as np
    import pandas as pd

    n = 40
    dates = pd.bdate_range("2024-01-02", periods=n)
    # 前20天缓慢下跌(MA5<MA20)，随后上涨(制造金叉)，再转跌(制造死叉)
    closes = np.concatenate(
        [
            np.linspace(52, 48, 20),   # 下跌段
            np.linspace(48, 65, 10),   # 上涨段：制造金叉
            np.linspace(65, 45, 10),   # 下跌段：制造死叉
        ]
    )

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
        df["rsi14"] = 50.0  # 固定值，本次自检只关心金叉/死叉路径，不触发RSI超买分支
        avg_vol5 = df["volume"].rolling(5, min_periods=5).mean().shift(1)
        df["volume_ratio5"] = df["volume"] / avg_vol5
        return df

    baseline_volume = np.full(n, 1_000_000)
    probe_df = _with_volume(baseline_volume)
    ma_diff = probe_df["ma5"] - probe_df["ma20"]
    golden_cross_day = ((ma_diff > 0) & (ma_diff.shift(1) <= 0)).idxmax()

    # 只在真正发生金叉的当天单独放量(其余天保持基准量)，确保 volume_ratio5(基于前5日
    # 均量，不含当日)在金叉当天确实 > 1.5倍，从而触发BUY
    volumes = baseline_volume.copy()
    volumes[golden_cross_day] = baseline_volume[golden_cross_day] * 5

    df = _with_volume(volumes)

    from strategies.ma_cross_rsi import generate_signals

    return generate_signals(df)


if __name__ == "__main__":
    main()
