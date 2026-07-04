"""绘制回测净值曲线(含最大回撤区间标注)。"""

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")


def plot_equity_curve(equity_curve: pd.DataFrame, out_path, metrics: dict | None = None, title: str | None = None):
    """equity_curve 需包含 date/equity 列；metrics 传入 backtest 的 metrics 字典时会
    在图上标出最大回撤区间。"""
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(equity_curve["date"], equity_curve["equity"], color="#4c72b0", linewidth=1.2, label="equity")

    if metrics and pd.notna(metrics.get("max_drawdown_peak_date")) and pd.notna(metrics.get("max_drawdown_trough_date")):
        ax.axvspan(
            metrics["max_drawdown_peak_date"],
            metrics["max_drawdown_trough_date"],
            color="red",
            alpha=0.15,
            label=f"max drawdown {metrics['max_drawdown']:.1%}",
        )

    ax.set_title(title or "Equity Curve")
    ax.set_xlabel("date")
    ax.set_ylabel("equity")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
