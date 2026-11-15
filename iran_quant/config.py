"""Read and validate user-editable YAML configuration.

Fail early on invalid configuration instead of silently changing strategy rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pandas as pd
import yaml


@dataclass(frozen=True)
class Asset:
    id: str
    symbol: str
    name: str
    type: str


@dataclass(frozen=True)
class Settings:
    project_name: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp | None
    sessions_per_year: int
    assets: tuple[Asset, ...]
    mode: str
    cache_max_age_hours: float
    request_timeout_seconds: float
    index_code: str
    strict_execution: bool
    momentum_sessions: int
    trend_sessions: int
    risk_sessions: int
    max_equities: int
    equity_sleeve: float
    gold_sleeve: float
    stock_weighting: str
    min_positive_momentum: float
    initial_capital_toman: float
    cost_bps_per_side: float

    @property
    def equity_ids(self) -> list[str]:
        return [asset.id for asset in self.assets if asset.type == 'equity']

    @property
    def gold_id(self) -> str:
        return next(asset.id for asset in self.assets if asset.type == 'gold')

    @property
    def defensive_id(self) -> str:
        return next(asset.id for asset in self.assets if asset.type == 'defensive')

    @property
    def asset_ids(self) -> list[str]:
        return [asset.id for asset in self.assets]


def load_config(path: Path, mode_override: str | None = None) -> Settings:
    with path.open(encoding='utf-8') as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise ValueError('YAML configuration must be a mapping')

    project = raw['project']
    market = raw['market_data']
    rules = raw['strategy']
    backtest = raw['backtest']
    assets = tuple(Asset(**record) for record in market['assets'])
    types = [asset.type for asset in assets]
    ids = [asset.id for asset in assets]
    if len(set(ids)) != len(ids):
        raise ValueError('Asset ids must be unique')
    if types.count('gold') != 1 or types.count('defensive') != 1 or not types.count('equity'):
        raise ValueError('Specify equities, exactly one gold ETF and one defensive ETF')
    if any(asset.type not in {'equity', 'gold', 'defensive'} for asset in assets):
        raise ValueError('Unknown asset type in configuration')

    mode = mode_override or market['mode']
    if mode not in {'live', 'demo'}:
        raise ValueError('market_data.mode must be live or demo')
    stock_weighting = rules['stock_weighting']
    if stock_weighting not in {'equal', 'inverse_vol'}:
        raise ValueError('stock_weighting must be equal or inverse_vol')
    eq_sleeve = float(rules['equity_sleeve'])
    gold_sleeve = float(rules['gold_sleeve'])
    if not (0 <= eq_sleeve <= 1 and 0 <= gold_sleeve <= 1 and eq_sleeve + gold_sleeve <= 1):
        raise ValueError('Investment sleeves must sum to at most 100%')
    for key in ('momentum_sessions', 'trend_sessions', 'risk_sessions', 'max_equities'):
        if int(rules[key]) < 1:
            raise ValueError(f'{key} must be positive')
    if rules['max_equities'] > types.count('equity'):
        raise ValueError('max_equities exceeds equity universe')
    end_date = pd.Timestamp(project['end_date']) if project['end_date'] else None
    start_date = pd.Timestamp(project['start_date'])
    if end_date is not None and end_date <= start_date:
        raise ValueError('end_date must be later than start_date')
    if float(backtest['cost_bps_per_side']) < 0:
        raise ValueError('Transaction cost must be nonnegative')
    if int(project['annual_trading_sessions']) <= 0:
        raise ValueError('annual_trading_sessions must be positive')

    return Settings(
        project_name=project['name'], start_date=start_date, end_date=end_date,
        sessions_per_year=int(project['annual_trading_sessions']), assets=assets,
        mode=mode, cache_max_age_hours=float(market['cache_max_age_hours']),
        request_timeout_seconds=float(market['request_timeout_seconds']),
        index_code=str(market['index_code']),
        strict_execution=bool(market['strict_execution']),
        momentum_sessions=int(rules['momentum_sessions']),
        trend_sessions=int(rules['trend_sessions']),
        risk_sessions=int(rules['risk_sessions']),
        max_equities=int(rules['max_equities']),
        equity_sleeve=eq_sleeve, gold_sleeve=gold_sleeve,
        stock_weighting=stock_weighting,
        min_positive_momentum=float(rules['min_positive_momentum']),
        initial_capital_toman=float(backtest['initial_capital_toman']),
        cost_bps_per_side=float(backtest['cost_bps_per_side']),
    )
