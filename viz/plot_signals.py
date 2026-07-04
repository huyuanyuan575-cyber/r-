"""在价格走势图上标注买卖点。"""

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")  # 无GUI环境下渲染到文件


def build_price_signal_figure(df: pd.DataFrame, symbol: str, title: str | None = None):
    """df 需包含 date/close/signal 列(signal 由 strategies.ma_cross_rsi.generate_signals 生成)。

    价格用折线图，BUY标绿色向上三角，SELL标红色向下三角，返回 matplotlib Figure
    (供 Streamlit st.pyplot() 直接展示，或由 plot_price_with_signals 保存成文件)。
    """
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df["date"], df["close"], color="#4c72b0", linewidth=1, label="close")

    buys = df[df["signal"] == "BUY"]
    sells = df[df["signal"] == "SELL"]
    ax.scatter(buys["date"], buys["close"], marker="^", color="green", s=90, label="BUY", zorder=3)
    ax.scatter(sells["date"], sells["close"], marker="v", color="red", s=90, label="SELL", zorder=3)

    ax.set_title(title or f"{symbol} 价格走势与买卖点")
    ax.set_xlabel("date")
    ax.set_ylabel("close")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def plot_price_with_signals(df: pd.DataFrame, symbol: str, out_path, title: str | None = None):
    """构建价格+买卖点图并保存为文件，返回 out_path。"""
    fig = build_price_signal_figure(df, symbol, title=title)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
