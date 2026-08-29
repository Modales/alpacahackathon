"""Disk cache for Alpaca daily bars — makes repeated validation runs fast."""
import hashlib

import pandas as pd

import alpaca_client
import config


def get_bars_cached(symbol, start, end, max_age_hours=12):
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(f"{symbol}|{start}|{end}".encode()).hexdigest()[:12]
    path = config.CACHE_DIR / f"{symbol}_{key}.csv"
    if path.exists():
        age = (pd.Timestamp.now().timestamp() - path.stat().st_mtime) / 3600
        if age < max_age_hours:
            return pd.read_csv(path)
    bars = alpaca_client.get_bars(symbol, "1Day", start=start, end=end)
    df = pd.DataFrame(bars)
    if len(df):
        df.to_csv(path, index=False)
    return df
