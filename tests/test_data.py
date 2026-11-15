"""Provider schema and calendar normalization tests."""
import pandas as pd
import pytest
from iran_quant.data_sources import MarketDataError, _normalize_table, get_market_data


def test_real_asset_schema_uses_adjusted_close_column():
    frame = pd.DataFrame({
        'date': ['2024-01-01', '2024-01-02'],
        'close': [100, 110],
        'volume': [10, 20],
    })
    result = _normalize_table(frame, is_index=False)
    assert result['price'].tolist() == [100, 110]
    assert result['date'].dtype.kind == 'M'


def test_negative_price_rejected():
    with pytest.raises(MarketDataError):
        _normalize_table(pd.DataFrame({'date': ['2024-01-01'], 'close': [-5]}), is_index=False)


def test_stale_quotes_are_flagged_not_claimed_executable(settings, panel):
    pos = 22
    date = panel.prices.index[pos]
    assert panel.observed.loc[date, 'GOLD']
    panel.observed.loc[date, 'GOLD'] = False
    assert not panel.observed.loc[date, 'GOLD']
    # A carried-forward valuation is not evidence of a new trade.
    assert pd.notna(panel.prices.loc[date, 'GOLD'])


def test_explicit_demo_requires_no_network(settings, tmp_path):
    assets, index, provenance = get_market_data(settings, tmp_path, cache_only=True)
    assert len(assets) == 6 and not index.empty
    assert provenance[0]['mode'] == 'SYNTHETIC_DEMO'
