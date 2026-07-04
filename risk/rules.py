"""风控规则配置，供 backtest.engine.run_backtest(risk_config=...) 使用。

规则：
    - max_position_pct：单只股票最大仓位不超过总资金(当前总资产)的这个比例
    - stop_loss_pct：单只股票浮亏超过这个比例时，强制卖出剩余全部持仓
    - take_profit_pct / take_profit_reduce_ratio：单只股票浮盈超过 take_profit_pct 时，
      按 take_profit_reduce_ratio 卖出对应比例的持仓(分批减仓)；每一笔持仓生命周期内
      只触发一次，不会每天重复减仓
    - portfolio_drawdown_halt_pct：账户总资产相对历史最高点的回撤超过这个比例时，
      暂停开新仓(只允许平仓/止损/止盈，不允许新的BUY)
"""

from dataclasses import dataclass


@dataclass
class RiskConfig:
    max_position_pct: float = 0.2
    stop_loss_pct: float = 0.08
    take_profit_pct: float = 0.30
    take_profit_reduce_ratio: float = 0.5
    portfolio_drawdown_halt_pct: float = 0.15
