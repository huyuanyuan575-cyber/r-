"""全局配置：数据路径、回测参数等非敏感设置。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_CACHE_DIR = PROJECT_ROOT / "data" / "cache"

# 回测默认参数
BACKTEST_START_DATE = "20230101"
BACKTEST_END_DATE = "20231231"
INITIAL_CAPITAL = 1_000_000

# 风控默认参数
MAX_POSITION_PCT = 0.2  # 单只股票最大仓位占比
STOP_LOSS_PCT = 0.1     # 止损比例
