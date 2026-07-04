"""Demo: 用 Tushare Pro 拉取贵州茅台(600519.SH)最近一年的前复权日线数据并存成 csv。

运行前需要:
1. 在 https://tushare.pro 注册账号并获取 token
2. 复制 config/secrets.example.py 为 config/secrets.py，填入 TUSHARE_TOKEN
"""

import sys
from datetime import datetime, timedelta

import tushare as ts

from config.settings import DATA_RAW_DIR

TS_CODE = "600519.SH"  # 贵州茅台


def load_token() -> str:
    try:
        from config.secrets import TUSHARE_TOKEN
    except ImportError:
        print(
            "未找到 config/secrets.py。请先执行:\n"
            "  cp config/secrets.example.py config/secrets.py\n"
            "然后在 config/secrets.py 中填入你的 TUSHARE_TOKEN（在 tushare.pro 个人主页获取）。"
        )
        sys.exit(1)

    if not TUSHARE_TOKEN:
        print("config/secrets.py 中的 TUSHARE_TOKEN 为空，请先填入你的 Tushare token。")
        sys.exit(1)

    return TUSHARE_TOKEN


def fetch_daily_bars(ts_code: str, years: int = 1):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years)
    return ts.pro_bar(
        ts_code=ts_code,
        adj="qfq",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )


def main():
    ts.set_token(load_token())

    df = fetch_daily_bars(TS_CODE)
    if df is None or df.empty:
        print("未获取到数据，请检查 token 是否有效、接口积分是否足够、网络是否可达 api.tushare.pro。")
        sys.exit(1)

    df = df.sort_values("trade_date")

    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_RAW_DIR / f"{TS_CODE.split('.')[0]}_daily_tushare.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"共获取 {len(df)} 条记录，已保存至: {out_path}")
    print(df.head())


if __name__ == "__main__":
    main()
