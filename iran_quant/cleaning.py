"""Validate, date-align and characterize the available trading histories."""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np
import pandas as pd
from .config import Settings


@dataclass
class MarketPanel:
    prices: pd.DataFrame
    observed: pd.DataFrame
    index: pd.Series
    quality: pd.DataFrame


def create_market_panel(asset_frames: dict[str, pd.DataFrame],
                        index_frame: pd.DataFrame, settings: Settings) -> MarketPanel:
    """Use exchange index sessions as the single calendar.

    Missing quotes on index sessions can mean a halt, not a zero-risk asset:
    prices are last-observation-carried-forward *for indicative valuation*;
    `observed` retains whether an asset really traded/was quoted that day.
    The backtester refuses to rebalance a nonquoted asset in strict mode.
    """
    index = index_frame.set_index('date')['price'].sort_index().astype(float)
    index = index.loc[index.index >= settings.start_date]
    if settings.end_date is not None:
        index = index.loc[index.index <= settings.end_date]
    if not index.index.is_unique or not index.index.is_monotonic_increasing:
        raise ValueError('Market index dates must be unique and increasing')
    if len(index) < max(settings.trend_sessions, settings.momentum_sessions) + 25:
        raise ValueError('Insufficient actual market sessions for indicator warm-up')

    prices, observed, quality = {}, {}, []
    for asset in settings.assets:
        frame = asset_frames[asset.id].set_index('date').sort_index()
        if frame.index.has_duplicates:
            raise ValueError(f'Duplicate history dates: {asset.id}')
        quoted = frame['price'].astype(float).reindex(index.index)
        volume = pd.to_numeric(frame['volume'], errors='coerce').reindex(index.index)
        # A reported price with zero/unknown trading volume is NOT an executable quote.
        obs = quoted.notna() & volume.gt(0).fillna(False)
        filled = quoted.ffill()    # Not treated as proof that a trade was possible.
        prices[asset.id] = filled
        observed[asset.id] = obs
        quoted_dates = quoted.dropna().index
        quality.append({
            'id': asset.id, 'symbol': asset.symbol, 'type': asset.type,
            'first_observed_date': str(quoted_dates.min().date()) if len(quoted_dates) else '',
            'last_observed_date': str(quoted_dates.max().date()) if len(quoted_dates) else '',
            'quoted_market_sessions': int(obs.sum()),
            'price_rows_without_positive_volume': int((quoted.notna() & ~obs).sum()),
            'market_sessions': int(len(index)),
            'quotation_coverage_fraction': round(float(obs.mean()), 4),
            'data_warning': 'Long halts and stale valuations require independent review',
        })
    prices_df = pd.DataFrame(prices, index=index.index)
    if (prices_df.min(skipna=True) <= 0).any():
        raise ValueError('Nonpositive price found after alignment')
    return MarketPanel(prices=prices_df,
                       observed=pd.DataFrame(observed, index=index.index),
                       index=index.rename('TEDPIX'), quality=pd.DataFrame(quality))
