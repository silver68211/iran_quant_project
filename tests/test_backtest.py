"""Protect execution timing, trading fees and portfolio cash accounting."""
from dataclasses import replace
import numpy as np
import pytest
from iran_quant.backtest import run_backtest, UntradableAssetError
from iran_quant.signals import make_signals


def test_accounting_matches_net_returns_and_fees(settings, panel):
    signals = make_signals(panel, settings)
    result = run_backtest(panel, signals, settings)
    hist = result.history
    assert np.isfinite(hist['nav']).all()
    assert (hist['nav'] > 0).all()
    assert np.allclose(result.holdings.sum(axis=1).values, 1.0)
    assert np.allclose(hist['nav'].pct_change().fillna(0), hist['daily_net_return'])
    assert len(result.trades) > 0
    assert (hist['cost_fraction'] >= 0).all()


def test_month_end_signal_executes_one_session_later(settings, panel):
    signals = make_signals(panel, settings)
    result = run_backtest(panel, signals, settings)
    first_signal = signals[0].date
    dates = panel.prices.index
    next_close = dates[dates.get_loc(first_signal) + 1]
    first_trade_date = result.trades.iloc[0]['date']
    assert first_trade_date == next_close
    assert result.holdings.loc[first_signal, 'CASH'] == 1.0
    # Trade at D+1 close cannot earn a D -> D+1 return.
    assert result.history.loc[next_close, 'daily_gross_return'] == 0.0
    assert result.history.loc[next_close, 'cost_fraction'] > 0


def test_fees_reduce_nav(settings, panel):
    signals = make_signals(panel, settings)
    costly = run_backtest(panel, signals, settings)
    free = run_backtest(panel, signals, replace(settings, cost_bps_per_side=0.0))
    assert costly.history['nav'].iloc[-1] < free.history['nav'].iloc[-1]


def test_unquoted_execution_is_rejected(settings, panel):
    signals = make_signals(panel, settings)
    first_signal = signals[0]
    execution = panel.prices.index[panel.prices.index.get_loc(first_signal.date) + 1]
    # A fresh defensive price is needed for first trade unless no allocation.
    panel.observed.loc[execution, settings.defensive_id] = False
    with pytest.raises(UntradableAssetError):
        run_backtest(panel, signals, settings)
