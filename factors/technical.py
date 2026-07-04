"""常用技术指标/因子计算。

输入统一约定：接收 data.cleaner.clean_daily_bars 清洗后的 DataFrame（按 date 升序，
至少包含 open/high/low/close/volume 列，停牌日为 NaN）。所有指标函数直接在停牌日
产生 NaN（依赖 pandas rolling/ewm 对 NaN 的默认传播行为），不做人工填充，避免把
停牌期间的“无效数据”伪装成真实信号。
"""

import numpy as np
import pandas as pd


def moving_average(df: pd.DataFrame, windows=(5, 10, 20, 60)) -> pd.DataFrame:
    """简单移动平均线 MA_n。"""
    df = df.copy()
    for window in windows:
        df[f"ma{window}"] = df["close"].rolling(window=window, min_periods=window).mean()
    return df


def ema(df: pd.DataFrame, windows=(12, 26)) -> pd.DataFrame:
    """指数移动平均线 EMA_n。"""
    df = df.copy()
    for window in windows:
        df[f"ema{window}"] = df["close"].ewm(span=window, adjust=False, min_periods=window).mean()
    return df


def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD：DIF、DEA(信号线)、MACD柱(2倍DIF-DEA)。"""
    df = df.copy()
    ema_fast = df["close"].ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False, min_periods=slow).mean()
    df["macd_dif"] = ema_fast - ema_slow
    df["macd_dea"] = df["macd_dif"].ewm(span=signal, adjust=False, min_periods=signal).mean()
    df["macd_hist"] = 2 * (df["macd_dif"] - df["macd_dea"])
    return df


def rsi(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """RSI 相对强弱指标（Wilder 平滑）。"""
    df = df.copy()
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss
    df[f"rsi{window}"] = 100 - (100 / (1 + rs))
    # 平均跌幅为0时 RS 为 inf：若同时平均涨幅也为0(窗口内价格完全走平)，涨跌力量相等，RSI应为50；
    # 否则(持续上涨、无下跌)RSI应为100。
    flat_price = (avg_gain == 0) & (avg_loss == 0)
    only_gains = (avg_loss == 0) & ~flat_price
    df.loc[flat_price, f"rsi{window}"] = 50
    df.loc[only_gains, f"rsi{window}"] = 100
    return df


def bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """布林带：中轨(MA)、上轨、下轨。"""
    df = df.copy()
    mid = df["close"].rolling(window=window, min_periods=window).mean()
    std = df["close"].rolling(window=window, min_periods=window).std()
    df[f"boll_mid{window}"] = mid
    df[f"boll_upper{window}"] = mid + num_std * std
    df[f"boll_lower{window}"] = mid - num_std * std
    return df


def momentum(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """动量因子：N日收益率 close[t] / close[t-N] - 1。"""
    df = df.copy()
    df[f"momentum{window}"] = df["close"].pct_change(periods=window)
    return df


def volatility(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """波动率因子：N日日收益率的滚动标准差(未年化)。"""
    df = df.copy()
    daily_return = df["close"].pct_change()
    df[f"volatility{window}"] = daily_return.rolling(window=window, min_periods=window).std()
    return df


def volume_ratio(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """量比因子：当日成交量 / 过去N日平均成交量。"""
    df = df.copy()
    avg_volume = df["volume"].rolling(window=window, min_periods=window).mean().shift(1)
    df[f"volume_ratio{window}"] = df["volume"] / avg_volume
    return df


def add_all_factors(df: pd.DataFrame) -> pd.DataFrame:
    """一次性叠加本模块的全部默认因子，便于demo/回测直接调用。"""
    df = moving_average(df)
    df = ema(df)
    df = macd(df)
    df = rsi(df)
    df = bollinger_bands(df)
    df = momentum(df)
    df = volatility(df)
    df = volume_ratio(df)
    return df
