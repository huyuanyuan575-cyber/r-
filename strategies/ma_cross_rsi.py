"""简单短线买卖点策略：MA5/MA20 金叉死叉 + 成交量确认 + RSI超买。

规则：
    买入(BUY): 当日 MA5 上穿 MA20(金叉)，且当日成交量 > 过去5日平均成交量的1.5倍
    卖出(SELL): 当日 MA5 下穿 MA20(死叉)，或者当日 RSI14 > 80(超买)
    其余: HOLD

无未来函数：金叉/死叉的判断只比较“当天”与“前一天”的 MA5-MA20 差值符号，
量比(volume_ratio5)本身就是用过去5日均量(不含当日)与当日成交量比较，
RSI14 只用当日及之前的收盘价滚动计算。整个函数不使用 shift(-1) 等任何
向未来看的操作，第 t 行的信号只依赖 df.iloc[:t+1] 的数据（tests/test_strategies.py
中有专门验证这一点的测试）。
"""

import pandas as pd


def generate_signals(
    df: pd.DataFrame,
    volume_ratio_threshold: float = 1.5,
    rsi_overbought: float = 80.0,
) -> pd.DataFrame:
    """输入需已包含 ma5/ma20/rsi14/volume_ratio5 列(见 factors.technical.add_all_factors)。

    输出新增 signal 列，取值 'BUY'/'SELL'/'HOLD'。指标历史不足(NaN)的交易日一律 HOLD。
    """
    required = {"ma5", "ma20", "rsi14", "volume_ratio5"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"缺少必要的指标列: {missing}，请先调用 factors.technical 相关函数计算")

    df = df.copy()

    ma_diff = df["ma5"] - df["ma20"]
    ma_diff_prev = ma_diff.shift(1)

    golden_cross = (ma_diff > 0) & (ma_diff_prev <= 0)
    death_cross = (ma_diff < 0) & (ma_diff_prev >= 0)

    buy_condition = golden_cross & (df["volume_ratio5"] > volume_ratio_threshold)
    sell_condition = death_cross | (df["rsi14"] > rsi_overbought)

    df["signal"] = "HOLD"
    # 死叉/超买优先于金叉：同一天若两种条件都触发，风控信号优先
    df.loc[buy_condition, "signal"] = "BUY"
    df.loc[sell_condition, "signal"] = "SELL"

    return df
