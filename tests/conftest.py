"""Shared small, deterministic fixtures for fast unit tests."""
from dataclasses import replace
from pathlib import Path
import pytest
from iran_quant.config import load_config
from iran_quant.cleaning import create_market_panel
from iran_quant.demo_data import make_demo_data


@pytest.fixture
def settings():
    root = Path(__file__).resolve().parents[1]
    raw = load_config(root / 'config' / 'strategy.yml', mode_override='demo')
    return replace(raw, start_date=__import__('pandas').Timestamp('2024-01-01'),
                   end_date=__import__('pandas').Timestamp('2024-10-31'),
                   momentum_sessions=7, trend_sessions=15, risk_sessions=7)


@pytest.fixture
def panel(settings):
    assets, benchmark = make_demo_data(settings)
    return create_market_panel(assets, benchmark, settings)
