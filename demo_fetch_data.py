"""Demo: 用 akshare 拉取贵州茅台(600519)最近一年的日线数据并存成 csv。"""

from datetime import datetime, timedelta

import akshare as ak

from config.settings import DATA_RAW_DIR

SYMBOL = "600519"  # 贵州茅台


def fetch_daily_bars(symbol: str, years: int = 1):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years)
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        adjust="qfq",
    )
    return df


def main():
    df = fetch_daily_bars(SYMBOL)

    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_RAW_DIR / f"{SYMBOL}_daily.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"共获取 {len(df)} 条记录，已保存至: {out_path}")
    print(df.head())


if __name__ == "__main__":
    main()
