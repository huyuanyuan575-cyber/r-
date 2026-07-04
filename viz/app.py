"""Streamlit 本地网页 - 页面1: 单只股票的价格走势 + 技术指标 + 买卖信号。

启动: streamlit run viz/app.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.cleaner import clean_daily_bars
from data.fetcher import fetch_daily_bars
from data.sample_data import build_sample_raw
from factors.technical import add_all_factors
from strategies.ma_cross_rsi import generate_signals
from viz.plot_signals import build_price_signal_figure

st.set_page_config(page_title="个人量化分析系统", layout="wide")

st.title("📈 股票走势 + 指标 + 买卖信号")

with st.sidebar:
    st.header("查询参数")
    symbol = st.text_input("股票代码(6位数字，如 600519)", value="600519")
    lookback_days = st.number_input("回看天数", min_value=90, max_value=1500, value=365, step=30)
    run_button = st.button("查询", type="primary")


@st.cache_data(show_spinner=False)
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
        st.session_state["_last_error"] = str(exc)

    cleaned_df = clean_daily_bars(raw_df, symbol=symbol)
    factor_df = add_all_factors(cleaned_df)
    signal_df = generate_signals(factor_df)
    return signal_df, is_real


if run_button or "signal_df" not in st.session_state:
    if not symbol:
        st.warning("请输入股票代码")
        st.stop()
    signal_df, is_real = load_signal_df(symbol, lookback_days)
    st.session_state["signal_df"] = signal_df
    st.session_state["is_real"] = is_real
    st.session_state["symbol"] = symbol

signal_df = st.session_state.get("signal_df")
is_real = st.session_state.get("is_real")
symbol = st.session_state.get("symbol", symbol)

if signal_df is None:
    st.info("在左侧输入股票代码并点击查询")
    st.stop()

if not is_real:
    st.warning(
        "无法连通真实数据源(akshare)，当前展示的是示例数据，不代表真实行情。"
        f"错误信息: {st.session_state.get('_last_error', '')}"
    )

fig = build_price_signal_figure(signal_df, symbol, title=f"{symbol} Price & Signals")
st.pyplot(fig)

col1, col2 = st.columns(2)
with col1:
    st.subheader("最新指标(最后10行)")
    show_cols = [
        "date", "close", "ma5", "ma10", "ma20", "ma60",
        "macd_dif", "macd_dea", "macd_hist", "rsi14",
        "boll_upper20", "boll_lower20", "volume_ratio5", "signal",
    ]
    st.dataframe(signal_df[show_cols].tail(10), use_container_width=True)

with col2:
    st.subheader("触发过的买卖信号")
    trades = signal_df[signal_df["signal"] != "HOLD"][["date", "close", "signal"]]
    if trades.empty:
        st.info("这段时间内没有触发任何BUY/SELL信号")
    else:
        st.dataframe(trades, use_container_width=True)
