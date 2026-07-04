"""批量拉取A股日线OHLCV数据(akshare)，带本地增量缓存，避免重复请求触发限流。

注意（前复权的一个重要陷阱）：
    akshare 的 qfq（前复权）价格以“最新交易日”为基准反算历史价格，一旦股票发生
    除权除息（送股/派息/配股），最新基准变化，会导致*历史*qfq价格整体发生一次性
    偏移。这意味着本模块缓存的 qfq 序列在跨越除权除息日之后会产生轻微不连续。
    对个人使用级别的分析这通常可以接受，但如果要做严格回测，建议在财报/除权
    公告后对相关标的调用 force_refresh=True 重新拉取全量历史，而不是完全依赖增量缓存。
"""

import time

import akshare as ak
import pandas as pd

from config.settings import DATA_RAW_DIR

COLUMN_MAP = {
    "日期": "date",
    "股票代码": "symbol",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
}

STANDARD_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "volume", "amount"]


def _raw_cache_path(symbol: str):
    return DATA_RAW_DIR / f"{symbol}_daily.csv"


def load_cached_raw(symbol: str) -> pd.DataFrame | None:
    """读取某只股票已缓存的原始日线数据，本地没有缓存则返回 None。"""
    path = _raw_cache_path(symbol)
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


def _save_cache(symbol: str, df: pd.DataFrame) -> None:
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(_raw_cache_path(symbol), index=False, encoding="utf-8-sig")


def _missing_ranges(cached: pd.DataFrame | None, start_ts: pd.Timestamp, end_ts: pd.Timestamp):
    """比较请求区间与已缓存区间，只返回真正缺失、需要请求接口的日期段。"""
    if cached is None or cached.empty:
        return [(start_ts, end_ts)]

    cached_min, cached_max = cached["date"].min(), cached["date"].max()
    ranges = []
    if start_ts < cached_min:
        ranges.append((start_ts, cached_min - pd.Timedelta(days=1)))
    if end_ts > cached_max:
        ranges.append((cached_max + pd.Timedelta(days=1), end_ts))
    return ranges


def fetch_daily_bars(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
    use_cache: bool = True,
    request_interval: float = 0.5,
) -> pd.DataFrame:
    """拉取单只股票的日线OHLCV(默认前复权)，本地已缓存的日期区间不会重新请求。"""
    start_ts, end_ts = pd.Timestamp(start_date), pd.Timestamp(end_date)
    cached = load_cached_raw(symbol) if use_cache else None

    ranges_to_fetch = _missing_ranges(cached, start_ts, end_ts) if use_cache else [(start_ts, end_ts)]

    fetched_frames = []
    for range_start, range_end in ranges_to_fetch:
        if range_start > range_end:
            continue
        raw = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=range_start.strftime("%Y%m%d"),
            end_date=range_end.strftime("%Y%m%d"),
            adjust=adjust,
        )
        time.sleep(request_interval)  # 请求间隔，降低被数据源限流的概率
        if raw is None or raw.empty:
            continue
        raw = raw.rename(columns=COLUMN_MAP)
        raw["date"] = pd.to_datetime(raw["date"])
        raw["symbol"] = symbol
        fetched_frames.append(raw[STANDARD_COLUMNS])

    if fetched_frames:
        new_data = pd.concat(fetched_frames, ignore_index=True)
        merged = pd.concat([cached, new_data], ignore_index=True) if cached is not None else new_data
        merged = merged.drop_duplicates(subset=["symbol", "date"]).sort_values("date").reset_index(drop=True)
        if use_cache:
            _save_cache(symbol, merged)
    else:
        merged = cached if cached is not None else pd.DataFrame(columns=STANDARD_COLUMNS)

    result = merged[(merged["date"] >= start_ts) & (merged["date"] <= end_ts)]
    return result.reset_index(drop=True)


def batch_fetch_daily_bars(
    symbols: list[str],
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
    use_cache: bool = True,
    request_interval: float = 0.5,
) -> dict[str, pd.DataFrame]:
    """批量拉取多只股票的日线数据，返回 {symbol: DataFrame}。"""
    return {
        symbol: fetch_daily_bars(
            symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            use_cache=use_cache,
            request_interval=request_interval,
        )
        for symbol in symbols
    }
