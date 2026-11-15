"""Single entry point connecting acquisition, cleaning, research and reporting."""
from __future__ import annotations
from pathlib import Path
import logging

from .backtest import run_backtest
from .cleaning import create_market_panel
from .config import Settings
from .data_sources import get_market_data
from .reporting import write_report
from .signals import make_signals

LOGGER = logging.getLogger(__name__)


def execute(settings: Settings, project_root: Path, output_dir: Path, *,
            refresh: bool = False, cache_only: bool = False) -> Path:
    LOGGER.info('Step 1/6: collecting %s market histories', settings.mode)
    assets, market_index, provenance = get_market_data(
        settings, project_root / 'data' / 'cache', refresh=refresh, cache_only=cache_only
    )
    LOGGER.info('Step 2/6: validating prices and calendar alignment')
    panel = create_market_panel(assets, market_index, settings)
    LOGGER.info('Step 3/6: estimating momentum, trend, and realized volatility')
    signals = make_signals(panel, settings)
    LOGGER.info('Step 4/6: creating monthly portfolio targets and delayed orders')
    LOGGER.info('Step 5/6: evaluating net of transaction costs')
    result = run_backtest(panel, signals, settings)
    LOGGER.info('Step 6/6: producing reproducible reports and performance figures')
    report_dir = write_report(result, panel, settings, provenance, output_dir)
    LOGGER.info('Success: %s (mode=%s)', report_dir.resolve(), settings.mode)
    return report_dir
