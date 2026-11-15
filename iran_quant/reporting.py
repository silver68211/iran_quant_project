"""Create figures, reproducible CSVs, research notes, and provenance manifests."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import logging

import matplotlib
matplotlib.use('Agg')  # Headless/SSH-safe chart generation.
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .backtest import BacktestResult
from .cleaning import MarketPanel
from .config import Settings
from .metrics import build_metrics
from .risk_model import asset_returns, covariance_at

LOGGER = logging.getLogger(__name__)


def write_report(result: BacktestResult, panel: MarketPanel, settings: Settings,
                 provenance: list[dict], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    history = result.history
    metrics = build_metrics(history, settings.sessions_per_year)
    history.to_csv(output_dir / 'daily_performance.csv')
    result.holdings.to_csv(output_dir / 'daily_holdings.csv')
    result.decisions.to_csv(output_dir / 'monthly_decisions.csv', index=False)
    result.trades.to_csv(output_dir / 'trades.csv', index=False)
    panel.quality.to_csv(output_dir / 'data_quality.csv', index=False)
    metrics.to_csv(output_dir / 'performance_metrics.csv')
    panel.prices.to_csv(output_dir / 'aligned_asset_prices.csv')
    panel.observed.astype(int).to_csv(output_dir / 'quotation_observed.csv')

    # Realized covariance is only defined if the latest 60 sessions are complete.
    try:
        cov = covariance_at(asset_returns(panel.prices), history.index[-1],
                            settings.risk_sessions, settings.sessions_per_year)
        cov.to_csv(output_dir / 'annualized_covariance.csv')
    except ValueError as error:
        LOGGER.warning('Covariance matrix not available: %s', error)

    latest_signal = result.signals[-1]
    latest_decision = result.decisions.iloc[-1]
    latest_target = {key.replace('target_', ''): float(val)
                     for key, val in latest_decision.items() if key.startswith('target_')}
    pd.Series(latest_target, name='target_weight').to_csv(output_dir / 'last_target_weights.csv')

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, layout='constrained')
    label = 'SYNTHETIC DATA (DEMO ONLY)' if settings.mode == 'demo' else 'TSETMC PUBLIC DATA'
    axes[0].plot(history.index, history['nav'], label='Systematic strategy (net fees)')
    axes[0].plot(history.index, history['TEDPIX_nav'], label='TEDPIX benchmark')
    axes[0].set_ylabel('Normalized wealth')
    axes[0].legend(loc='best')
    axes[0].grid(alpha=0.2)
    axes[0].set_title(f'{settings.project_name} | {label}')
    for name, field in [('Strategy', 'nav'), ('TEDPIX', 'TEDPIX_nav')]:
        path = history[field]
        axes[1].plot(history.index, 100 * (path / path.cummax() - 1), label=name)
    axes[1].set_ylabel('Drawdown (%)')
    axes[1].set_xlabel('Gregorian date')
    axes[1].legend(loc='best')
    axes[1].grid(alpha=0.2)
    fig.savefig(output_dir / 'performance_and_drawdowns.png', dpi=170)
    plt.close(fig)

    manifest = {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'mode': 'SYNTHETIC_DEMO_NO_MARKET_DATA' if settings.mode == 'demo' else 'LIVE_TSETMC_PUBLIC_DATA',
        'project_name': settings.project_name,
        'first_backtest_date': str(history.index.min().date()),
        'last_backtest_date': str(history.index.max().date()),
        'last_signal_date': str(latest_signal.date.date()),
        'latest_target_weights': latest_target,
        'sources': provenance,
        'assumptions': [
            'All closing price rows use Gregorian exchange-session dates.',
            'Asset series are provider-adjusted; adjustment methodology needs validation.',
            'Trade signals use closing data through D, execute at close of next session D+1.',
            'Execution price is proxied by adjusted close, not a documented achievable fill.',
            'A missing daily quotation is carried forward for indicative marking only.',
            'No purchases/sales in assets lacking an observed quote on rebalance date.',
            'No order-book depth, price-limit queue, taxes, tracking error, or liquidity impact modeling.',
            'Portfolio is value-weighted, weights drift until monthly rebalancing.',
            'Annualization assumes configured sessions/year, not an exact calendar-year calculation.',
            'Only price-based TEDPIX benchmark is compared; index method may differ from fund total returns.',
            'Current fixed universe may introduce survivorship/selection bias.',
            'Inflation and FX adjustments are outside the core backtest.',
        ],
    }
    (output_dir / 'run_manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding='utf-8'
    )
    as_pct = lambda x: f'{x:.2%}'
    note = [
        f'# {settings.project_name}', '',
        f'**Data mode: {manifest["mode"]}**', '',
        f'Backtest: {history.index.min():%Y-%m-%d} to {history.index.max():%Y-%m-%d}.', '',
        '## Performance (illustrative research backtest, not investment advice)', '',
        '| Statistic | Strategy, net fees | TEDPIX |',
        '|---|---:|---:|',
    ]
    for key in ['total_return', 'cagr', 'annualized_volatility', 'sharpe_zero_rf', 'max_drawdown']:
        a, b = metrics.loc[key, 'Strategy_net'], metrics.loc[key, 'TEDPIX_index']
        fmt = (lambda n: f'{n:.2f}') if key == 'sharpe_zero_rf' else as_pct
        note.append(f'| {key} | {fmt(a)} | {fmt(b)} |')
    note.extend([
        '', '## Latest completed-month target (not a trade instruction)', '',
        f'Signal was calculated at the {latest_signal.date:%Y-%m-%d} market close.', '',
        '| Asset | Target |', '|---|---:|',
    ])
    for key, weight in latest_target.items():
        note.append(f'| {key} | {weight:.1%} |')
    note += ['', '## Important limitations', '']
    note += [f'- {assumption}' for assumption in manifest['assumptions']]
    note += ['', '### Source provenance', '',
             'See `run_manifest.json` for fetch dates, provider details and original data sources.', '']
    (output_dir / 'RESEARCH_REPORT.md').write_text('\n'.join(note), encoding='utf-8')
    return output_dir
