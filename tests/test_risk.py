"""对 backtest/engine.py 里风控规则(risk.rules.RiskConfig)的自测。

用法: python tests/test_risk.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest.engine import run_backtest
from risk.rules import RiskConfig

SYMBOL = "600519"
ZERO_COST_KWARGS = dict(
    buy_commission_rate=0.0,
    sell_commission_rate=0.0,
    stamp_duty_rate=0.0,
    slippage_rate=0.0,
)


def _row(date, close, pct_chg, signal):
    return {"date": pd.Timestamp(date), "close": close, "pct_chg": pct_chg, "signal": signal}


def test_stop_loss_forces_sell_even_without_signal():
    df = pd.DataFrame(
        [
            _row("2024-01-02", 100.0, np.nan, "HOLD"),
            _row("2024-01-03", 100.0, 0.0, "BUY"),
            _row("2024-01-04", 95.0, -0.05, "HOLD"),   # 浮亏5%，未到止损线
            _row("2024-01-05", 91.0, (91 - 95) / 95, "HOLD"),  # 相对买入价浮亏9%，超过8%止损线
        ]
    )
    risk_config = RiskConfig(stop_loss_pct=0.08)
    result = run_backtest(
        df, SYMBOL, initial_capital=100_000, max_position_pct=1.0, risk_config=risk_config, **ZERO_COST_KWARGS
    )
    assert len(result.trades) == 1, "浮亏超过止损线时，即使策略信号是HOLD也应强制卖出"
    assert result.trades[0].exit_reason == "STOP_LOSS"
    assert result.trades[0].exit_date == pd.Timestamp("2024-01-05")
    print("test_stop_loss_forces_sell_even_without_signal: PASS")


def test_take_profit_reduces_half_once_then_signal_sells_rest():
    df = pd.DataFrame(
        [
            _row("2024-01-02", 100.0, np.nan, "HOLD"),
            _row("2024-01-03", 100.0, 0.0, "BUY"),
            _row("2024-01-04", 135.0, 0.35, "HOLD"),  # 浮盈35%，触发止盈减仓一半
            _row("2024-01-05", 150.0, 150 / 135 - 1, "HOLD"),  # 浮盈更高，但止盈只触发一次
            _row("2024-01-08", 148.0, 148 / 150 - 1, "SELL"),  # 策略自身信号卖出剩余持仓
        ]
    )
    risk_config = RiskConfig(take_profit_pct=0.30, take_profit_reduce_ratio=0.5)
    result = run_backtest(
        df, SYMBOL, initial_capital=100_000, max_position_pct=1.0, risk_config=risk_config, **ZERO_COST_KWARGS
    )
    assert len(result.trades) == 2, "应该是：止盈减半 1笔 + 策略卖出剩余 1笔"
    first, second = result.trades
    assert first.exit_reason == "TAKE_PROFIT"
    assert first.exit_date == pd.Timestamp("2024-01-04")
    assert second.exit_reason == "SIGNAL_SELL"
    assert second.exit_date == pd.Timestamp("2024-01-08")
    # 买入1000股(10万/100，无手续费情形)，止盈应卖出一半500股，剩余500股留到最后卖出
    assert first.shares == 500
    assert second.shares == 500
    print("test_take_profit_reduces_half_once_then_signal_sells_rest: PASS")


def test_portfolio_drawdown_halt_blocks_new_buy_but_not_close():
    # stop_loss_pct 故意设成99%(相当于关闭)，只隔离测试"组合总回撤熔断"这一条规则：
    # 用连续几天温和下跌(每天都在10%涨跌停以内，不会被涨跌停规则挡住)累积出一个较大的
    # 亏损，由策略自身的SELL信号平仓，制造出 >15% 的组合总回撤，再看后续BUY是否被挡住。
    df = pd.DataFrame(
        [
            _row("2024-01-02", 100.0, np.nan, "HOLD"),
            _row("2024-01-03", 100.0, 0.0, "BUY"),
            _row("2024-01-04", 92.0, -0.08, "HOLD"),
            _row("2024-01-05", 84.0, (84 - 92) / 92, "HOLD"),
            _row("2024-01-08", 76.0, (76 - 84) / 84, "SELL"),   # 累计浮亏24%，策略自身平仓
            _row("2024-01-09", 80.0, 80 / 76 - 1, "BUY"),        # 回撤超过15%后尝试重新开仓
            _row("2024-01-10", 88.0, 0.10, "SELL"),
        ]
    )
    # 两组配置只有 portfolio_drawdown_halt_pct 不同：一组15%(会被24%回撤触发熔断)，
    # 一组99%(实际上不可能触发，相当于关闭熔断)
    halted = run_backtest(
        df, SYMBOL, initial_capital=100_000, max_position_pct=1.0,
        risk_config=RiskConfig(stop_loss_pct=0.99, portfolio_drawdown_halt_pct=0.15), **ZERO_COST_KWARGS
    )
    not_halted = run_backtest(
        df, SYMBOL, initial_capital=100_000, max_position_pct=1.0,
        risk_config=RiskConfig(stop_loss_pct=0.99, portfolio_drawdown_halt_pct=0.99), **ZERO_COST_KWARGS
    )

    # 熔断组：第4笔交易日的亏损平仓后回撤超过15%，第6天的BUY应被阻止，交易总数停在1笔
    assert len(halted.trades) == 1
    assert halted.equity_curve["equity"].iloc[-1] == 76_000.0, "熔断后应保持空仓，权益不再变化"

    # 未熔断组：回撤24% < 99%阈值，不阻止；第6天正常开新仓，第7天SELL信号正常平仓
    assert len(not_halted.trades) == 2
    assert not_halted.trades[1].exit_reason == "SIGNAL_SELL"
    assert not_halted.equity_curve["equity"].iloc[-1] != 76_000.0, "未熔断时应该有新开仓+平仓，权益应变化"
    print("test_portfolio_drawdown_halt_blocks_new_buy_but_not_close: PASS")


def main():
    test_stop_loss_forces_sell_even_without_signal()
    test_take_profit_reduces_half_once_then_signal_sells_rest()
    test_portfolio_drawdown_halt_blocks_new_buy_but_not_close()
    print("\n全部测试通过。")


if __name__ == "__main__":
    main()
