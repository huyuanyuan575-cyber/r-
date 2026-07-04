"""Streamlit 本地网页 - 页面3: 回测报告(净值曲线 + 关键指标表格)。"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backtest.engine import run_backtest
from data.cleaner import clean_daily_bars
from data.fetcher import fetch_daily_bars
from data.sample_data import build_sample_raw
from factors.technical import add_all_factors
from risk.rules import RiskConfig
from strategies.ma_cross_rsi import generate_signals
from viz.plot_equity import build_equity_figure

st.set_page_config(page_title="回测报告", layout="wide")
st.title("🧪 回测报告")

with st.sidebar:
    st.header("回测参数")
    symbol = st.text_input("股票代码", value="600519")
    lookback_days = st.number_input("回看天数", min_value=180, max_value=1500, value=730, step=30)
    initial_capital = st.number_input("初始资金(元)", min_value=10_000, value=100_000, step=10_000)
    max_position_pct = st.slider("单次买入仓位上限(占总资产比例)", 0.05, 1.0, 0.2, 0.05)

    st.divider()
    use_risk = st.checkbox("叠加风控规则", value=False)
    stop_loss_pct = st.slider("止损线(浮亏)", 0.02, 0.30, 0.08, 0.01, disabled=not use_risk)
    take_profit_pct = st.slider("止盈线(浮盈)", 0.05, 1.0, 0.30, 0.05, disabled=not use_risk)
    take_profit_reduce_ratio = st.slider("止盈减仓比例", 0.1, 1.0, 0.5, 0.1, disabled=not use_risk)
    portfolio_drawdown_halt_pct = st.slider("组合回撤熔断线", 0.05, 0.50, 0.15, 0.01, disabled=not use_risk)

    run_button = st.button("运行回测", type="primary")


def load_signal_df(symbol: str, lookback_days: int):
    end = datetime.now()
    start = end - timedelta(days=lookback_days)
    try:
        raw_df = fetch_daily_bars(symbol, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        if raw_df.empty:
            raise RuntimeError("接口返回空数据")
        is_real = True
    except Exception as exc:
        raw_df = build_sample_raw(symbol, periods=max(lookback_days // 2, 60), suspension_indices=(), anomaly_index=None)
        is_real = False
        st.session_state["_bt_last_error"] = str(exc)

    cleaned_df = clean_daily_bars(raw_df, symbol=symbol)
    factor_df = add_all_factors(cleaned_df)
    signal_df = generate_signals(factor_df)
    return signal_df, is_real


if run_button:
    signal_df, is_real = load_signal_df(symbol, lookback_days)

    risk_config = None
    if use_risk:
        risk_config = RiskConfig(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            take_profit_reduce_ratio=take_profit_reduce_ratio,
            portfolio_drawdown_halt_pct=portfolio_drawdown_halt_pct,
        )

    result = run_backtest(
        signal_df, symbol, initial_capital=initial_capital, max_position_pct=max_position_pct, risk_config=risk_config
    )
    st.session_state["bt_result"] = result
    st.session_state["bt_symbol"] = symbol
    st.session_state["bt_is_real"] = is_real

result = st.session_state.get("bt_result")
if result is None:
    st.info("在左侧设置参数，点击'运行回测'")
    st.stop()

if not st.session_state.get("bt_is_real"):
    st.warning(
        "无法连通真实数据源(akshare)，当前用的是示例数据，回测结论不代表真实行情。"
        f"错误信息: {st.session_state.get('_bt_last_error', '')}"
    )

m = result.metrics
cols = st.columns(6)
cols[0].metric("总收益率", f"{m['total_return']:.2%}")
cols[1].metric("年化收益率", f"{m['annualized_return']:.2%}" if pd.notna(m["annualized_return"]) else "N/A")
cols[2].metric("最大回撤", f"{m['max_drawdown']:.2%}" if pd.notna(m["max_drawdown"]) else "N/A")
cols[3].metric("夏普比率", f"{m['sharpe_ratio']:.2f}" if pd.notna(m["sharpe_ratio"]) else "N/A")
cols[4].metric("胜率", f"{m['win_rate']:.2%}" if pd.notna(m["win_rate"]) else "N/A")
cols[5].metric("交易次数", m["num_trades"])

st.pyplot(build_equity_figure(result.equity_curve, metrics=m, title=f"{st.session_state.get('bt_symbol')} Equity Curve"))

st.subheader("交易明细")
trades_df = result.trades_df()
if trades_df.empty:
    st.info("这段时间内没有已平仓的交易")
else:
    st.dataframe(trades_df, use_container_width=True)
