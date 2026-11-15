"""Estimate realized volatility and covariance, with no future observations."""
import numpy as np
import pandas as pd


def asset_returns(prices: pd.DataFrame) -> pd.DataFrame:
    # fill_method=None prevents silently bridging missing pre-listing prices.
    return prices.pct_change(fill_method=None)


def rolling_volatility(prices: pd.DataFrame, window: int, sessions_per_year: int) -> pd.DataFrame:
    returns = asset_returns(prices)
    return returns.rolling(window=window, min_periods=window).std() * np.sqrt(sessions_per_year)


def covariance_at(returns: pd.DataFrame, asof: pd.Timestamp, window: int,
                  sessions_per_year: int) -> pd.DataFrame:
    """Estimated annual covariance matrix up to and including `asof`."""
    sample = returns.loc[:asof].tail(window).dropna(axis=0, how='any')
    if len(sample) < window:
        raise ValueError('Insufficient complete observations to estimate covariance')
    return sample.cov() * sessions_per_year
