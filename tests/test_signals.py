"""Test month-end selection and point-in-time decision invariants."""
from dataclasses import replace
import numpy as np
import pandas as pd
from iran_quant.signals import make_signals, Signal
from iran_quant.allocation import target_weights


def test_signals_exclude_incomplete_last_month(settings, panel):
    signals = make_signals(panel, settings)
    assert signals
    assert signals[-1].date.to_period('M') < panel.prices.index[-1].to_period('M')


def test_no_lookahead_changes_to_future_prices(settings, panel):
    early = make_signals(panel, settings)[0]
    modified = panel.prices.copy()
    modified.loc[modified.index > early.date, 'FOOLAD'] *= 20
    from iran_quant.cleaning import MarketPanel
    altered = MarketPanel(modified, panel.observed, panel.index, panel.quality)
    same_early = make_signals(altered, settings)[0]
    assert early.selected_equities == same_early.selected_equities
    assert early.gold_positive == same_early.gold_positive
    assert early.market_is_positive == same_early.market_is_positive


def test_negative_market_trend_blocks_equity_sleeve(settings):
    signal = Signal(
        pd.Timestamp('2024-05-31'), False, ('FOOLAD', 'FMLI'), True,
        {'FOOLAD': 0.2, 'FMLI': 0.1}, {'FOOLAD': 0.2, 'FMLI': 0.3},
        1000.0, 1200.0,
    )
    weights = target_weights(signal, settings)
    assert weights['FOOLAD'] == 0
    assert weights['FMLI'] == 0
    assert np.isclose(weights['GOLD'], 0.3)
    assert np.isclose(weights['DEFENSIVE'], 0.7)


def test_one_positive_equity_invests_only_half_equity_budget(settings):
    signal = Signal(
        pd.Timestamp('2024-05-31'), True, ('FOOLAD',), False,
        {'FOOLAD': 0.2}, {'FOOLAD': 0.25}, 1200.0, 1000.0,
    )
    weights = target_weights(signal, settings)
    assert weights['FOOLAD'] == 0.25
    assert weights['DEFENSIVE'] == 0.75
    assert np.isclose(weights.sum(), 1)
