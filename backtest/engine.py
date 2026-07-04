"""单标的、事件驱动的回测引擎，模拟A股实盘交易的主要约束。

模拟的约束：
    - 交易成本：买入手续费万3；卖出手续费万3 + 印花税千1
    - 滑点：按成交价上下浮动0.1%（买入按更差的价格成交，卖出同理）
    - A股 T+1：当天买入的股票，当天不能卖出
    - 涨跌停：当天涨跌幅达到该股票理论涨跌停幅度时，对应方向视为无法成交
      (涨停当天没有对手卖盘，无法买入；跌停当天没有对手买盘，无法卖出)
    - 仓位限制：单次买入金额不超过"当前总资产"(现金+持仓市值)的 max_position_pct，
      且按A股100股一手取整，不足一手的部分不买

简化假设（个人量化分析可接受，严格实盘还需更精细的撮合模型）：
    - 信号在第 t 天收盘后产生(基于当天收盘价)，也在第 t 天收盘价(+滑点)成交，
      不做"信号次日执行"的延迟建模
    - 单标的、只做多、不加杠杆、不做金字塔加仓：同一时间最多持有一笔仓位，
      收到 BUY 时若已持仓则忽略，收到 SELL 时若空仓则忽略
    - 涨跌停当天若信号被阻止成交，直接放弃这次交易机会，不做"次日补单"
    - 停牌日(收盘价 NaN)不产生任何交易，净值按最后一个有效收盘价markToMarket结转
"""

from dataclasses import dataclass, field
from math import floor

import numpy as np
import pandas as pd

from data.cleaner import price_limit_pct

BUY_COMMISSION_RATE = 0.0003
SELL_COMMISSION_RATE = 0.0003
STAMP_DUTY_RATE = 0.001
SLIPPAGE_RATE = 0.001
LOT_SIZE = 100
TRADING_DAYS_PER_YEAR = 252


@dataclass
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp
    exit_price: float
    shares: int
    cost_basis: float
    net_proceeds: float
    pnl: float
    return_pct: float


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame  # 列: date, equity
    trades: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def trades_df(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame(
                columns=[
                    "entry_date", "entry_price", "exit_date", "exit_price",
                    "shares", "cost_basis", "net_proceeds", "pnl", "return_pct",
                ]
            )
        return pd.DataFrame([t.__dict__ for t in self.trades])


def run_backtest(
    signal_df: pd.DataFrame,
    symbol: str,
    initial_capital: float = 100_000.0,
    max_position_pct: float = 0.2,
    buy_commission_rate: float = BUY_COMMISSION_RATE,
    sell_commission_rate: float = SELL_COMMISSION_RATE,
    stamp_duty_rate: float = STAMP_DUTY_RATE,
    slippage_rate: float = SLIPPAGE_RATE,
    lot_size: int = LOT_SIZE,
    risk_free_rate: float = 0.0,
) -> BacktestResult:
    """跑一遍单标的回测。signal_df 需按 date 升序，至少包含 date/close/pct_chg/signal 列
    (即 strategies.ma_cross_rsi.generate_signals 的输出)。"""
    df = signal_df.sort_values("date").reset_index(drop=True)
    limit = price_limit_pct(symbol)
    limit_tolerance = 0.001  # 涨跌幅在理论涨跌停附近的容差，避免因浮点/复权误差漏判

    cash = initial_capital
    shares_held = 0
    entry_date = None
    entry_price = None
    cost_basis = 0.0
    last_valid_price = None

    trades: list[Trade] = []
    equity_records = []

    for _, row in df.iterrows():
        date = row["date"]
        price = row["close"]
        pct_chg = row.get("pct_chg", np.nan)
        signal = row.get("signal", "HOLD")

        if pd.notna(price):
            last_valid_price = price

            is_limit_up = pd.notna(pct_chg) and pct_chg >= limit - limit_tolerance
            is_limit_down = pd.notna(pct_chg) and pct_chg <= -(limit - limit_tolerance)

            if signal == "BUY" and shares_held == 0 and not is_limit_up:
                total_equity = cash + shares_held * price
                investable = min(cash, max_position_pct * total_equity)
                buy_price = price * (1 + slippage_rate)
                max_shares = investable / (buy_price * (1 + buy_commission_rate))
                shares_to_buy = floor(max_shares / lot_size) * lot_size

                if shares_to_buy >= lot_size:
                    gross_cost = shares_to_buy * buy_price
                    commission = gross_cost * buy_commission_rate
                    total_spent = gross_cost + commission

                    cash -= total_spent
                    shares_held = shares_to_buy
                    entry_date = date
                    entry_price = buy_price
                    cost_basis = total_spent

            elif signal == "SELL" and shares_held > 0 and date != entry_date and not is_limit_down:
                sell_price = price * (1 - slippage_rate)
                gross_proceeds = shares_held * sell_price
                commission = gross_proceeds * sell_commission_rate
                stamp_duty = gross_proceeds * stamp_duty_rate
                net_proceeds = gross_proceeds - commission - stamp_duty

                pnl = net_proceeds - cost_basis
                return_pct = pnl / cost_basis if cost_basis else np.nan

                trades.append(
                    Trade(
                        entry_date=entry_date,
                        entry_price=entry_price,
                        exit_date=date,
                        exit_price=sell_price,
                        shares=shares_held,
                        cost_basis=cost_basis,
                        net_proceeds=net_proceeds,
                        pnl=pnl,
                        return_pct=return_pct,
                    )
                )

                cash += net_proceeds
                shares_held = 0
                entry_date = None
                entry_price = None
                cost_basis = 0.0

        mark_price = last_valid_price if last_valid_price is not None else 0.0
        equity = cash + shares_held * mark_price
        equity_records.append({"date": date, "equity": equity})

    equity_curve = pd.DataFrame(equity_records)
    metrics = _compute_metrics(equity_curve, trades, initial_capital, risk_free_rate)

    return BacktestResult(equity_curve=equity_curve, trades=trades, metrics=metrics)


def _max_drawdown(equity_series: pd.Series):
    running_max = equity_series.cummax()
    drawdown = equity_series / running_max - 1
    trough_idx = drawdown.idxmin()
    max_dd = drawdown.loc[trough_idx]
    peak_idx = equity_series.loc[:trough_idx].idxmax()
    return max_dd, peak_idx, trough_idx


def _compute_metrics(equity_curve: pd.DataFrame, trades: list, initial_capital: float, risk_free_rate: float) -> dict:
    equity_series = equity_curve.set_index("date")["equity"]
    num_days = len(equity_series)
    final_equity = equity_series.iloc[-1] if num_days else initial_capital

    total_return = final_equity / initial_capital - 1
    annualized_return = (
        (final_equity / initial_capital) ** (TRADING_DAYS_PER_YEAR / num_days) - 1
        if num_days > 0 and final_equity > 0
        else np.nan
    )

    max_dd, peak_date, trough_date = (np.nan, None, None)
    if num_days > 1:
        max_dd, peak_idx, trough_idx = _max_drawdown(equity_series)
        peak_date, trough_date = peak_idx, trough_idx

    daily_returns = equity_series.pct_change().dropna()
    daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess_returns = daily_returns - daily_rf
    sharpe_ratio = (
        excess_returns.mean() / excess_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
        if len(excess_returns) > 1 and excess_returns.std() > 0
        else np.nan
    )

    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    win_rate = len(wins) / len(pnls) if pnls else np.nan
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = np.mean(losses) if losses else 0.0
    profit_loss_ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else np.nan

    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_dd,
        "max_drawdown_peak_date": peak_date,
        "max_drawdown_trough_date": trough_date,
        "sharpe_ratio": sharpe_ratio,
        "win_rate": win_rate,
        "profit_loss_ratio": profit_loss_ratio,
        "num_trades": len(trades),
        "final_equity": final_equity,
    }


def format_report(result: BacktestResult, symbol: str) -> str:
    m = result.metrics
    lines = [
        f"=== {symbol} 回测报告 ===",
        f"总收益率: {m['total_return']:.2%}",
        f"年化收益率: {m['annualized_return']:.2%}" if pd.notna(m["annualized_return"]) else "年化收益率: N/A",
        (
            f"最大回撤: {m['max_drawdown']:.2%} "
            f"({m['max_drawdown_peak_date'].date()} -> {m['max_drawdown_trough_date'].date()})"
            if pd.notna(m["max_drawdown"])
            else "最大回撤: N/A"
        ),
        f"夏普比率: {m['sharpe_ratio']:.2f}" if pd.notna(m["sharpe_ratio"]) else "夏普比率: N/A",
        f"胜率: {m['win_rate']:.2%}" if pd.notna(m["win_rate"]) else "胜率: N/A(无已平仓交易)",
        (
            f"盈亏比: {m['profit_loss_ratio']:.2f}"
            if pd.notna(m["profit_loss_ratio"])
            else "盈亏比: N/A(无亏损交易或无交易)"
        ),
        f"交易次数: {m['num_trades']}",
        f"期末资产: {m['final_equity']:,.2f}",
    ]
    return "\n".join(lines)
