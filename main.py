#!/usr/bin/env python3
"""Run the complete Tehran quantitative-strategy research workflow.

Examples:
    python main.py                         # LIVE data; no synthetic fallback
    python main.py --mode demo             # deterministic offline validation
    python main.py --refresh               # ignore 24h market-data cache
    python main.py --cache-only            # use only previously saved real data
    python main.py --config config/strategy.yml --output outputs/my_run
"""
from __future__ import annotations
import argparse
import logging
from pathlib import Path

from iran_quant.config import load_config
from iran_quant.pipeline import execute

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config' / 'strategy.yml')
    parser.add_argument('--mode', choices=('live', 'demo'), help='Override data mode in YAML')
    parser.add_argument('--refresh', action='store_true', help='Redownload live histories')
    parser.add_argument('--cache-only', action='store_true', help='Forbid network requests')
    parser.add_argument('--output', type=Path, help='Output folder (defaults to outputs/live or outputs/demo)')
    parser.add_argument('--verbose', action='store_true', help='Extra debugging logs')
    args = parser.parse_args()
    if args.refresh and args.cache_only:
        parser.error('--refresh and --cache-only cannot be combined')
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')
    settings = load_config(args.config, mode_override=args.mode)
    output_dir = args.output or ROOT / 'outputs' / settings.mode
    execute(settings, ROOT, output_dir, refresh=args.refresh, cache_only=args.cache_only)
    print(f'\nReport: {(output_dir / "RESEARCH_REPORT.md").resolve()}')
    print(f'Chart:  {(output_dir / "performance_and_drawdowns.png").resolve()}')
    if settings.mode == 'demo':
        print('CAUTION: This run uses SYNTHETIC data and is NOT real Iranian market performance.')


if __name__ == '__main__':
    main()
