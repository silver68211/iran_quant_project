"""Translate quantitative signals into fully invested target weights."""
from __future__ import annotations

import numpy as np
import pandas as pd
from .config import Settings
from .signals import Signal


def target_weights(signal: Signal, settings: Settings) -> pd.Series:
    weights = pd.Series(0.0, index=settings.asset_ids, dtype=float)
    selected = signal.selected_equities if signal.market_is_positive else ()
    if selected:
        # If fewer than max_equities qualify, leave the unused sleeve defensive.
        equity_budget = settings.equity_sleeve * (len(selected) / settings.max_equities)
        if settings.stock_weighting == 'inverse_vol':
            inverse = np.array([1.0 / max(signal.volatility[a], 1e-8) for a in selected])
            shares = inverse / inverse.sum()
        else:
            shares = np.full(len(selected), 1 / len(selected))
        for name, share in zip(selected, shares):
            weights.loc[name] = equity_budget * share
    if signal.gold_positive:
        weights.loc[settings.gold_id] = settings.gold_sleeve
    weights.loc[settings.defensive_id] = 1 - weights.sum()
    if (weights < -1e-12).any() or not np.isclose(weights.sum(), 1.0):
        raise ValueError('Invalid allocation: weights must be nonnegative and total 100%')
    return weights
