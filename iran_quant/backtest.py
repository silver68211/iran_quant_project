"""Walk-forward, end-of-day portfolio simulator with explicit execution lag.

Timing:
    At close D: compute a signal from data through D.
    At close D+1: trade at next-session prices (approximated by closing marks).
    During D+2: begin earning returns attributable to the new holdings.

Adjusted historical closes are used as proxies for execution prices; that is an
important limitation, particularly for Iranian price limits and suspended names.
"""
from __future__ import annotations
from dataclasses import dataclass
import logging

import numpy as np
import pandas as pd

from .allocation import target_weights
from .cleaning import MarketPanel
from .config import Settings
from .signals import Signal

LOGGER = logging.getLogger(__name__)


class UntradableAssetError(RuntimeError):
    """A trade was requested in a security without an exchange quotation."""


@dataclass
class BacktestResult:
    history: pd.DataFrame
    holdings: pd.DataFrame
    trades: pd.DataFrame
    decisions: pd.DataFrame
    signals: list[Signal]


def run_backtest(panel: MarketPanel, signals: list[Signal], settings: Settings) -> BacktestResult:
    index = panel.prices.index
    ids = settings.asset_ids
    first_signal_pos = index.get_loc(signals[0].date)
    if first_signal_pos >= len(index) - 1:
        raise ValueError('No following session available for first order')

    # Each monthly close signal becomes an order at the NEXT market close.
    orders: dict[pd.Timestamp, tuple[Signal, pd.Series]] = {}
    decision_rows = []
    for signal in signals:
        signal_pos = index.get_loc(signal.date)
        target = target_weights(signal, settings)
        if signal_pos + 1 >= len(index):
            continue  # Cannot trade based on a signal with no next observed session.
        execution_date = index[signal_pos + 1]
        orders[execution_date] = (signal, target)
        decision_rows.append({
            'signal_date': signal.date, 'execution_date': execution_date,
            'market_is_positive': signal.market_is_positive,
            'selected_equities': ','.join(signal.selected_equities),
            'gold_positive': signal.gold_positive,
            'TEDPIX': signal.market_level, 'market_MA': signal.trend_average,
            **{f'target_{key}': float(value) for key, value in target.items()},
        })

    # Start after the first valid signal with only zero-return, not-invested CASH.
    # Cash is an accounting placeholder, distinct from the fixed-income ETF.
    current = pd.Series(0.0, index=ids + ['CASH'])
    current.loc['CASH'] = 1.0
    nav = 1.0
    histories = [{
        'date': index[first_signal_pos], 'nav': nav, 'daily_net_return': 0.0,
        'daily_gross_return': 0.0, 'cost_fraction': 0.0,
        'turnover': 0.0, 'stale_held_assets': 0,
        'TEDPIX_nav': 1.0,
    }]
    holdings = [{'date': index[first_signal_pos], **current.to_dict()}]
    trades = []
    benchmark_base = panel.index.iloc[first_signal_pos]

    for pos in range(first_signal_pos + 1, len(index)):
        today, yesterday = index[pos], index[pos - 1]
        previous_nav = nav
        now_prices, prev_prices = panel.prices.loc[today], panel.prices.loc[yesterday]
        # Stale/suspended quotes are carried forward only for indicative mark-to-market.
        asset_daily_returns = now_prices.div(prev_prices).sub(1)
        active = current.loc[ids] > 1e-12
        if asset_daily_returns.loc[active[active].index].isna().any():
            raise ValueError(f'Missing valuation data for an owned security on {today.date()}')
        asset_daily_returns = asset_daily_returns.fillna(0.0)
        daily_gross = float((current.loc[ids] * asset_daily_returns).sum())
        nav *= 1 + daily_gross
        if nav <= 0:
            raise ValueError('Portfolio net asset value became nonpositive')
        # The weight of a winner rises and that of a loser falls between trades.
        drifted = current.copy()
        drifted.loc[ids] = current.loc[ids] * (1 + asset_daily_returns) / (1 + daily_gross)
        drifted.loc['CASH'] = current.loc['CASH'] / (1 + daily_gross)
        stale_count = int((active & ~panel.observed.loc[today]).sum())

        traded_notional_fraction = 0.0
        cost_fraction = 0.0
        if today in orders:
            signal, target_assets = orders[today]
            target = pd.concat([target_assets, pd.Series({'CASH': 0.0})])
            changes = target - drifted
            changed_ids = [name for name in ids if abs(changes[name]) > 1e-10]
            blocked = [name for name in changed_ids if not panel.observed.loc[today, name]]
            if blocked:
                message = f'{today.date()}: no executable quotation for {blocked}'
                if settings.strict_execution:
                    raise UntradableAssetError(message)
                LOGGER.warning('%s; skipping entire rebalance (not filling at stale prices)', message)
            else:
                # Per-side fee is assessed on buys PLUS sells in real instruments.
                # Do not charge a fake trading fee on the accounting CASH balance.
                traded_notional_fraction = float(changes.loc[ids].abs().sum())
                cost_fraction = traded_notional_fraction * settings.cost_bps_per_side / 10_000
                if cost_fraction >= 1:
                    raise ValueError('Configured fees make execution impossible')
                before_fee_nav = nav
                nav *= (1 - cost_fraction)
                for name in changed_ids:
                    trades.append({
                        'date': today, 'signal_date': signal.date,
                        'asset': name, 'action': 'BUY' if changes[name] > 0 else 'SELL',
                        'weight_change': float(changes[name]),
                        'notional_toman': float(abs(changes[name]) * before_fee_nav * settings.initial_capital_toman),
                        'execution_assumption': 'next-session adjusted close proxy',
                    })
                drifted = target

        current = drifted
        if not np.isclose(current.sum(), 1.0, atol=1e-9):
            raise ValueError('Internal accounting error: weights do not sum to 100%')
        histories.append({
            'date': today, 'nav': float(nav),
            'daily_net_return': float(nav / previous_nav - 1),
            'daily_gross_return': daily_gross,
            'cost_fraction': cost_fraction,
            'turnover': traded_notional_fraction,
            'stale_held_assets': stale_count,
            'TEDPIX_nav': float(panel.index.loc[today] / benchmark_base),
        })
        holdings.append({'date': today, **current.to_dict()})

    history = pd.DataFrame(histories).set_index('date')
    history['capital_toman'] = history['nav'] * settings.initial_capital_toman
    return BacktestResult(
        history=history,
        holdings=pd.DataFrame(holdings).set_index('date'),
        trades=pd.DataFrame(trades, columns=[
            'date', 'signal_date', 'asset', 'action', 'weight_change',
            'notional_toman', 'execution_assumption',
        ]),
        decisions=pd.DataFrame(decision_rows), signals=signals,
    )
