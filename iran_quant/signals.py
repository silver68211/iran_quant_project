"""Build month-end momentum and broad-market trend signals.

No decision includes information observed AFTER the close of its signal date.
"""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from .cleaning import MarketPanel
from .config import Settings
from .risk_model import rolling_volatility


@dataclass(frozen=True)
class Signal:
    date: pd.Timestamp
    market_is_positive: bool
    selected_equities: tuple[str, ...]
    gold_positive: bool
    momentum: dict[str, float]
    volatility: dict[str, float]
    market_level: float
    trend_average: float


def make_signals(panel: MarketPanel, settings: Settings) -> list[Signal]:
    prices = panel.prices
    momentum = prices.div(prices.shift(settings.momentum_sessions)) - 1
    trend = panel.index.rolling(settings.trend_sessions,
                              min_periods=settings.trend_sessions).mean()
    volatility = rolling_volatility(prices, settings.risk_sessions, settings.sessions_per_year)

    # Last trading session of each *completed* Gregorian calendar month. The
    # final month in any fetched panel may be incomplete; exclude it safely.
    all_dates = prices.index
    completed = all_dates[all_dates.to_period('M') != all_dates[-1].to_period('M')]
    month_ends = pd.Series(completed, index=completed).groupby(completed.to_period('M')).last()
    results: list[Signal] = []
    for date in month_ends:
        market_level = panel.index.loc[date]
        avg = trend.loc[date]
        if pd.isna(avg):
            continue
        mom = momentum.loc[date]
        vol = volatility.loc[date]
        eligible = [name for name in settings.equity_ids
                    if bool(panel.observed.loc[date, name])
                    and pd.notna(mom[name]) and pd.notna(vol[name])
                    and mom[name] > settings.min_positive_momentum]
        ranked = sorted(eligible, key=lambda name: (-float(mom[name]), name))
        gold = settings.gold_id
        results.append(Signal(
            date=date,
            market_is_positive=bool(market_level > avg),
            selected_equities=tuple(ranked[:settings.max_equities]),
            gold_positive=bool(panel.observed.loc[date, gold]
                               and pd.notna(mom[gold])
                               and mom[gold] > settings.min_positive_momentum),
            momentum={name: float(v) for name, v in mom.dropna().items()},
            volatility={name: float(v) for name, v in vol.dropna().items()},
            market_level=float(market_level), trend_average=float(avg),
        ))
    if not results:
        raise ValueError('No completed month-end signals after warm-up; extend history')
    return results
