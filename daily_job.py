"""每日收盘后任务：更新关注股票数据 -> 重新计算指标和信号 -> 把当天新出现的
买卖信号整理成文字摘要，保存为 markdown 文件。

用法：
    python daily_job.py            # 立即手动跑一次(测试用)
    python daily_job.py --schedule  # 常驻进程，用 APScheduler 按cron定时每个交易日自动跑一次
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from config.settings import REPORTS_DIR
from data.cleaner import clean_daily_bars
from data.fetcher import fetch_daily_bars
from factors.technical import add_all_factors
from strategies.ma_cross_rsi import generate_signals

WATCHLIST = ["600519", "000858", "601318", "300750", "000001"]
LOOKBACK_DAYS = 400  # 保证MA60/RSI14等长周期指标有足够历史可算


def process_symbol(symbol: str, lookback_days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    """更新单只股票的数据(增量缓存)，重新计算指标和信号，返回完整signal_df。"""
    end = datetime.now()
    start = end - timedelta(days=lookback_days)
    raw_df = fetch_daily_bars(symbol, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
    if raw_df.empty:
        raise RuntimeError("接口返回空数据")

    cleaned_df = clean_daily_bars(raw_df, symbol=symbol)
    factor_df = add_all_factors(cleaned_df)
    return generate_signals(factor_df)


def build_summary_markdown(results: dict, as_of: datetime | None = None) -> str:
    """把每只股票"最新一天"的信号整理成markdown文字摘要。

    results: {symbol: signal_df 或 None(处理失败)}
    """
    as_of = as_of or datetime.now()
    lines = [f"# 每日买卖信号摘要 - {as_of.strftime('%Y-%m-%d')}", ""]

    triggered = []
    holding = []
    failed = []

    for symbol, signal_df in results.items():
        if signal_df is None or signal_df.empty:
            failed.append(symbol)
            continue

        latest = signal_df.sort_values("date").iloc[-1]
        if latest["signal"] in ("BUY", "SELL"):
            triggered.append((symbol, latest))
        else:
            holding.append((symbol, latest))

    lines.append("## 今日新出现的买卖信号")
    if triggered:
        for symbol, row in triggered:
            lines.append(
                f"- **{symbol}**：{row['signal']} @ {row['close']:.2f}"
                f"（交易日 {pd.Timestamp(row['date']).date()}）"
            )
    else:
        lines.append("今天没有股票触发新的 BUY/SELL 信号。")

    lines.append("")
    lines.append("## 其余关注股票(无新信号)")
    if holding:
        for symbol, row in holding:
            lines.append(f"- {symbol}：HOLD，最新收盘 {row['close']:.2f}（{pd.Timestamp(row['date']).date()}）")
    else:
        lines.append("(无)")

    if failed:
        lines.append("")
        lines.append("## 数据获取失败，本次跳过")
        for symbol in failed:
            lines.append(f"- {symbol}")

    return "\n".join(lines)


def run_daily_job(symbols: list | None = None) -> Path:
    symbols = symbols or WATCHLIST
    results = {}
    for symbol in symbols:
        try:
            results[symbol] = process_symbol(symbol)
        except Exception as exc:
            print(f"{symbol}: 处理失败 - {exc}")
            results[symbol] = None

    summary = build_summary_markdown(results)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"daily_signals_{datetime.now().strftime('%Y%m%d')}.md"
    out_path.write_text(summary, encoding="utf-8")

    print(f"摘要已保存: {out_path}\n")
    print(summary)
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", action="store_true", help="常驻进程，按cron定时自动运行，而不是立即跑一次")
    parser.add_argument("--cron-hour", type=int, default=15, help="定时任务的小时(默认15，对应A股收盘后)")
    parser.add_argument("--cron-minute", type=int, default=30, help="定时任务的分钟(默认30)")
    args = parser.parse_args()

    if not args.schedule:
        run_daily_job()
        return

    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        run_daily_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=args.cron_hour,
        minute=args.cron_minute,
    )
    print(
        f"定时任务已启动：每个交易日(周一至周五) {args.cron_hour:02d}:{args.cron_minute:02d} "
        "(Asia/Shanghai) 自动运行一次。按 Ctrl+C 停止。"
    )
    scheduler.start()


if __name__ == "__main__":
    main()
