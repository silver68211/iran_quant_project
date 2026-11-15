"""Fully SYNTHETIC quotes for deterministic, offline pipeline tests.

The demonstration never represents simulated observations as real Iranian prices.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from .config import Settings


def make_demo_data(settings: Settings) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    rng = np.random.default_rng(20261115)
    start = settings.start_date
    end = settings.end_date or pd.Timestamp('2025-12-31')
    dates = pd.date_range(start, end, freq='D')
    # Saturday-Wednesday is the standard Tehran exchange session pattern.
    dates = dates[dates.weekday.isin([5, 6, 0, 1, 2])]
    n = len(dates)
    if n < max(settings.trend_sessions, settings.momentum_sessions) + 45:
        raise ValueError('Demo date range is too short for indicator warm-up')

    # Correlated simulated regimes: down years and up years, NOT historical observations.
    regime = np.where(np.arange(n) % 320 < 200, 0.0010, -0.0005)
    market_r = np.clip(regime + rng.normal(0, 0.013, n), -0.12, 0.12)
    market = pd.DataFrame({'date': dates, 'price': 1_000_000 * np.cumprod(1 + market_r)})

    result = {}
    equity_betas = [1.05, 1.15, 0.85, 1.30]
    for i, asset in enumerate(settings.assets):
        if asset.type == 'equity':
            beta = equity_betas[settings.equity_ids.index(asset.id) % len(equity_betas)]
            r = np.clip(beta * market_r + rng.normal(0, 0.012, n), -0.22, 0.22)
        elif asset.type == 'gold':
            r = np.clip(0.0008 - 0.15 * market_r + rng.normal(0, 0.008, n), -0.12, 0.12)
        else:
            r = np.clip(0.00065 + rng.normal(0, 0.00008, n), -0.01, 0.01)
        result[asset.id] = pd.DataFrame({
            'date': dates,
            'price': (10000 + 2500 * i) * np.cumprod(1 + r),
            'volume': rng.integers(50_000, 2_000_000, n),
        })
    return result, market
