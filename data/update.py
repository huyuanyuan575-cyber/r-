"""增量更新日线数据：只补齐本地缓存最新日期到今天之间缺失的数据，不重新下载全部历史。

可以配合 crontab / 系统计划任务每天收盘后跑一次，例如：
    0 16 * * 1-5  cd /path/to/project && venv/bin/python -m data.update
"""

import sys
from datetime import datetime

from data.fetcher import fetch_daily_bars, load_cached_raw

DEFAULT_SYMBOLS = ["600519", "000858", "601318", "300750", "000001"]
# 仅在本地完全没有缓存时用作首次拉取的起始日期；已有缓存的股票只会从缓存的
# 最新日期往后补齐，不会重新下载这个起始日期之前的数据。
DEFAULT_HISTORY_START = "20200101"


def update_symbol(symbol: str, adjust: str = "qfq"):
    today = datetime.now().strftime("%Y%m%d")
    before = load_cached_raw(symbol)
    before_max = before["date"].max() if before is not None and not before.empty else None

    df = fetch_daily_bars(
        symbol,
        start_date=DEFAULT_HISTORY_START,
        end_date=today,
        adjust=adjust,
        use_cache=True,
    )

    after_max = df["date"].max() if not df.empty else None
    added = len(df) - (len(before) if before is not None else 0)
    print(
        f"{symbol}: 缓存前最新日期={before_max.date() if before_max is not None else '无'}, "
        f"更新后最新日期={after_max.date() if after_max is not None else '无'}, "
        f"新增 {max(added, 0)} 条，共 {len(df)} 条"
    )
    return df


def main(symbols=None):
    symbols = symbols or DEFAULT_SYMBOLS
    for symbol in symbols:
        try:
            update_symbol(symbol)
        except Exception as exc:
            print(f"{symbol}: 更新失败 - {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
