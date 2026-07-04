"""Streamlit 本地网页 - 页面2: 多因子选股排名表(估值 + 动量 + 波动率)。"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from demo_multi_factor_score import fake_fundamentals_provider, fake_ohlcv_provider, SAMPLE_FUNDAMENTALS
from strategies.multi_factor_score import score_stocks

st.set_page_config(page_title="多因子选股排名", layout="wide")
st.title("🏆 多因子长线选股排名")

DEFAULT_SYMBOLS = "600519,000858,601318,300750,000001"

with st.sidebar:
    st.header("查询参数")
    symbols_text = st.text_input("股票代码(逗号分隔)", value=DEFAULT_SYMBOLS)
    as_of_date = st.date_input("截止日期")
    use_sample = st.checkbox(
        "使用示例数据(真实数据源不可达时勾选，或想快速看效果时勾选)", value=True
    )
    run_button = st.button("计算排名", type="primary")

if run_button:
    symbols = [s.strip() for s in symbols_text.split(",") if s.strip()]
    date_str = as_of_date.strftime("%Y-%m-%d")

    if use_sample:
        unknown = [s for s in symbols if s not in SAMPLE_FUNDAMENTALS]
        if unknown:
            st.error(
                f"示例数据模式只内置了 {list(SAMPLE_FUNDAMENTALS.keys())} 这几只股票的示意性基本面/走势数据，"
                f"不认识: {unknown}。取消勾选'使用示例数据'以尝试真实数据源，或换成内置的股票代码。"
            )
            st.stop()
        result = score_stocks(
            symbols, date_str, ohlcv_provider=fake_ohlcv_provider, fundamentals_provider=fake_fundamentals_provider
        )
        st.warning("当前展示的是示例数据：行业分类为真实公开信息，PE和价格走势为示意性数值，不代表真实行情。")
    else:
        try:
            result = score_stocks(symbols, date_str)
        except Exception as exc:
            st.error(f"真实数据源拉取失败: {exc}\n请勾选'使用示例数据'来查看排名逻辑的演示效果。")
            st.stop()

    st.session_state["score_result"] = result

result = st.session_state.get("score_result")
if result is None:
    st.info("在左侧设置股票代码和日期，点击'计算排名'")
    st.stop()

st.subheader("排名表(点击列名可按该因子排序)")
st.dataframe(result, use_container_width=True)

st.subheader("因子说明")
st.markdown(
    """
    - **valuation_zscore(估值)**：PE(TTM)越低越好，在**同行业内**做zscore；行业内只有1只样本股时记为中性0
    - **momentum_zscore(动量)**：过去60个交易日涨幅，越高越好，在整个股票池内做zscore
    - **volatility_zscore(波动率)**：过去60个交易日收益率标准差，越低越好，在整个股票池内做zscore
    - **composite_score**：三项按权重(默认各1/3)加权求和，从高到低排名
    """
)
