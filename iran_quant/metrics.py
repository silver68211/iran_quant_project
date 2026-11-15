"""Consistent performance measures for strategy and benchmark paths."""
from __future__ import annotations
import numpy as np
import pandas as pd


def evaluate_nav(nav: pd.Series, sessions_per_year: int) -> dict[str, float]:
    nav = nav.dropna().astype(float)
    if len(nav) < 2 or nav.le(0).any():
        raise ValueError('Positive NAV observations are required')
    daily_returns = nav.pct_change(fill_method=None).dropna()
    total_return = nav.iloc[-1] / nav.iloc[0] - 1
    years = len(daily_returns) / sessions_per_year
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1
    vol = daily_returns.std(ddof=1) * np.sqrt(sessions_per_year)
    # Zero risk-free assumption ONLY; annualized excess Sharpe would need a
    # matching contemporaneous daily risk-free rate, not a constant annual one.
    sharpe = daily_returns.mean() / daily_returns.std(ddof=1) * np.sqrt(sessions_per_year)
    if not np.isfinite(sharpe):
        sharpe = np.nan
    drawdown = nav / nav.cummax() - 1
    return {
        'total_return': float(total_return),
        'cagr': float(cagr),
        'annualized_volatility': float(vol),
        'sharpe_zero_rf': float(sharpe),
        'max_drawdown': float(drawdown.min()),
        'observations': float(len(daily_returns)),
    }


def build_metrics(history: pd.DataFrame, sessions_per_year: int) -> pd.DataFrame:
    strategy = evaluate_nav(history['nav'], sessions_per_year)
    benchmark = evaluate_nav(history['TEDPIX_nav'], sessions_per_year)
    return pd.DataFrame({'Strategy_net': strategy, 'TEDPIX_index': benchmark})
