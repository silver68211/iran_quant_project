"""Public Iranian market-data access with a transparent on-disk cache.

Live mode uses pytse-client for adjusted fund/stock history and TSETMC's public
index endpoint. Any failure is reported; synthetic prices are NEVER substituted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Settings
from .demo_data import make_demo_data

LOGGER = logging.getLogger(__name__)
INDEX_URL = 'https://cdn.tsetmc.com/api/Index/GetIndexB2History/{code}'


class MarketDataError(RuntimeError):
    """A source, cache, or market-data schema is unusable."""


def _normalize_table(frame: pd.DataFrame, *, is_index: bool) -> pd.DataFrame:
    """Convert provider-specific rows to consistent date/price(/volume) columns."""
    if frame is None or frame.empty:
        raise MarketDataError('Provider returned an empty price history')
    frame = frame.copy()
    frame.columns = [str(col).strip() for col in frame.columns]
    if 'date' not in frame.columns:
        if isinstance(frame.index, pd.DatetimeIndex):
            frame = frame.reset_index().rename(columns={frame.index.name or 'index': 'date'})
        else:
            raise MarketDataError(f'No Gregorian date column: {list(frame.columns)}')
    if 'price' not in frame.columns:
        # pytse-client with adjust=True supplies the adjusted `close` series.
        # TSETMC index has the `xNivInuClMresIbs` field instead.
        candidates = ('xNivInuClMresIbs', 'Adj Close', 'close') if is_index else ('close',)
        chosen = next((c for c in candidates if c in frame.columns), None)
        if chosen is None:
            raise MarketDataError(f'No expected closing price column: {list(frame.columns)}')
        frame = frame.rename(columns={chosen: 'price'})
    frame['date'] = pd.to_datetime(frame['date'], errors='coerce').dt.normalize()
    frame['price'] = pd.to_numeric(frame['price'], errors='coerce')
    if 'volume' not in frame.columns:
        frame['volume'] = pd.NA
    frame['volume'] = pd.to_numeric(frame['volume'], errors='coerce')
    frame = frame[['date', 'price', 'volume']].dropna(subset=['date', 'price'])
    frame = frame.sort_values('date').drop_duplicates(subset='date', keep='last')
    if frame.empty or (frame['price'] <= 0).any():
        raise MarketDataError('Price series is empty or includes nonpositive values')
    if (frame['volume'].dropna() < 0).any():
        raise MarketDataError('Volume series has negative values')
    return frame.reset_index(drop=True)


def _tsetmc_index(settings: Settings) -> pd.DataFrame:
    """Download actual TEDPIX/index history from the public HTTPS JSON endpoint."""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retry))
    url = INDEX_URL.format(code=settings.index_code)
    response = session.get(url, timeout=settings.request_timeout_seconds, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; AcademicResearch/1.0)',
        'Accept': 'application/json',
    })
    response.raise_for_status()
    payload = response.json()
    rows = payload.get('indexB2', [])
    if not rows:
        raise MarketDataError(f'Unexpected index response from {url}')
    index = pd.DataFrame(rows)
    required = {'dEven', 'xNivInuClMresIbs'}
    if not required.issubset(index.columns):
        raise MarketDataError(f'Index JSON missing {required - set(index.columns)}')
    dates = pd.to_datetime(index['dEven'].astype(str), format='%Y%m%d', errors='coerce')
    normalized = pd.DataFrame({'date': dates, 'price': index['xNivInuClMresIbs']})
    return _normalize_table(normalized, is_index=True)


def _tsetmc_asset(symbol: str) -> pd.DataFrame:
    """Use pytse-client's adjusted history, including the exchange's rial quotes.

    Adjusted prices are used for return calculations; they are NOT prices that
    could have been executed historically. Normalization avoids mixing the two.
    """
    try:
        import pytse_client as tse
    except ImportError as error:
        raise MarketDataError('Install pytse-client as specified in environment.yml') from error

    histories = tse.download(symbols=symbol, write_to_csv=False, adjust=True)
    if not isinstance(histories, dict) or not histories:
        raise MarketDataError(f'No history returned for symbol {symbol!r}')
    # Provider symbols can vary in Arabic/Persian variants of yeh/kaf.
    canonical = lambda s: str(s).replace('ي', 'ی').replace('ك', 'ک').strip()
    match = next((frame for key, frame in histories.items() if canonical(key) == canonical(symbol)), None)
    if match is None:
        raise MarketDataError(f'Provider did not return the requested symbol {symbol!r}')
    return _normalize_table(match, is_index=False)


def _load_or_fetch(cache_dir: Path, key: str, settings: Settings, *, symbol: str | None,
                   cache_only: bool, refresh: bool) -> tuple[pd.DataFrame, dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_file = cache_dir / f'{key}.csv'
    metadata_file = cache_dir / f'{key}.json'
    have_cache = csv_file.is_file() and metadata_file.is_file()
    metadata: dict = {}
    if have_cache:
        metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
        # Never reuse cached prices after the asset symbol or index code changes.
        expected_source = ('pytse-client / TSETMC' if symbol else
                           INDEX_URL.format(code=settings.index_code))
        if metadata.get('symbol') != symbol or metadata.get('source') != expected_source:
            raise MarketDataError(
                f'Cache identity changed for {key}; remove its two cache files or use a new asset ID'
            )
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(metadata['fetched_utc'])).total_seconds() / 3600
        if (not refresh and age <= settings.cache_max_age_hours) or cache_only:
            LOGGER.info('Using cached history for %s (age %.1f hours)', key, age)
            return _normalize_table(pd.read_csv(csv_file), is_index=(symbol is None)), metadata

    if cache_only:
        raise MarketDataError(f'Missing cache for {key}; run without --cache-only first')

    LOGGER.info('Downloading public market history: %s', symbol or 'TEDPIX')
    try:
        frame = _tsetmc_asset(symbol) if symbol else _tsetmc_index(settings)
    except Exception as exc:
        raise MarketDataError(
            f'Could not retrieve real data for {key}: {exc}. '
            'Network access to Iranian exchanges can be restricted. '
            'A previous verified cache can be used with --cache-only.'
        ) from exc
    metadata = {
        'key': key,
        'symbol': symbol,
        'source': 'pytse-client / TSETMC' if symbol else INDEX_URL.format(code=settings.index_code),
        'fetched_utc': datetime.now(timezone.utc).isoformat(),
        'adjustment': 'provider-adjusted closing prices' if symbol else 'reported index level',
        'mode': 'LIVE_REAL_MARKET_DATA',
        'first_date': str(frame['date'].min().date()),
        'last_date': str(frame['date'].max().date()),
        'rows': len(frame),
    }
    frame.to_csv(csv_file, index=False)
    metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return frame, metadata


def get_market_data(settings: Settings, cache_dir: Path, *, cache_only: bool = False,
                    refresh: bool = False) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, list[dict]]:
    """Load every required instrument and the index; fail if any is unavailable."""
    if settings.mode == 'demo':
        assets, index = make_demo_data(settings)
        return assets, index, [{'mode': 'SYNTHETIC_DEMO', 'source': 'seeded numpy RNG'}]

    assets: dict[str, pd.DataFrame] = {}
    provenance: list[dict] = []
    for asset in settings.assets:
        frame, meta = _load_or_fetch(cache_dir, f'asset_{asset.id}', settings,
                                    symbol=asset.symbol, cache_only=cache_only, refresh=refresh)
        assets[asset.id] = frame
        provenance.append(meta)
        time.sleep(0.4)  # Avoid unnecessarily fast requests to public services.
    index, meta = _load_or_fetch(cache_dir, 'index_TEDPIX', settings,
                                 symbol=None, cache_only=cache_only, refresh=refresh)
    provenance.append(meta)
    return assets, index, provenance
