# Tehran systematic multi-asset portfolio — Python research project

A documented, modular, reproducible **research backtest** for a rules-based
Iranian investment portfolio. It uses publicly accessible Tehran Stock Exchange
(TSETMC) histories for real runs, and an explicitly labeled synthetic simulator
for offline tests. It **does not place orders or promise investment returns**.

## Start here

Create the dedicated Conda environment and run from the project root:

```bash
conda env create -f environment.yml
conda activate iran-quant
python -m pytest -q
python main.py --mode demo   # Runs everywhere; synthetic data, not actual market returns
python main.py               # Attempts LIVE TSETMC download and historical backtest
```

You only need `python main.py`: `main.py` automatically connects all the
modules in their correct order, downloads or loads cache, validates histories,
builds signals, simulates the strategy, evaluates it, and saves charts and
reports. There are **no manual notebook cells** to execute.

If the network permits, the live run writes to `outputs/live/`.
If access to exchange data is restricted, the live run **fails clearly**;
it never silently replaces missing real quotations with fabricated data.

Optional commands:

```bash
python main.py --refresh                 # Force new downloads
python main.py --cache-only              # Re-run with previously downloaded real data
python main.py --mode demo               # Offline deterministic sample
python main.py --output outputs/trial_01 # Choose output directory
python main.py --config config/strategy.yml
```

> **Data-source verification limitation:** The pipeline, chart generation, and
> tests were executed successfully with **synthetic** data. The live TSETMC
> endpoint could not be reached from the environment in which this project was
> created. Real Iranian-market downloads and live-mode backtest figures have
> therefore **not** been validated here. APIs and accessibility may change.

## Project files

```text
iran_quant_project/
├── main.py                        # Single command-line entry point
├── environment.yml                # Dedicated reproducible Conda environment
├── Makefile                       # Short aliases for test/demo/live
├── config/
│   └── strategy.yml               # Assets, lookbacks, allocations, fees, dates
├── iran_quant/
│   ├── config.py                   # Validate and type-check YAML settings
│   ├── data_sources.py            # Live TSETMC, adjusted prices, disk cache
│   ├── demo_data.py               # Explicitly synthetic offline data generator
│   ├── cleaning.py                # Sessions, missing records, quality checks
│   ├── risk_model.py              # Volatility, realized covariance matrix
│   ├── signals.py                 # Monthly momentum and 200-day market filter
│   ├── allocation.py              # Equity / gold / defensive ETF target weights
│   ├── backtest.py                # Delayed execution, drifting holdings, costs
│   ├── metrics.py                 # Return, annualized vol, Sharpe, drawdown
│   ├── reporting.py               # CSVs, PNGs, markdown report, source manifest
│   └── pipeline.py                # Calls each module in sequence
├── tests/                         # Automated regression / bias / execution tests
├── data/cache/                    # Live provider histories (created on first run)
└── outputs/demo/                  # Included EXAMPLE output, explicitly synthetic
```

## Real financial instruments (Persian exchange symbols)

| Model ID | Symbol | Category | Role |
|---|---|---|---|
| FOOLAD | فولاد | Equity | Steel-sector exposure |
| FMLI | فملی | Equity | Copper / mining exposure |
| WBMLT | وبملت | Equity | Banking exposure |
| SHPNA | شپنا | Equity | Refining exposure |
| GOLD | طلا | Gold ETF | Domestic gold exposure |
| DEFENSIVE | یاقوت | Fixed-income ETF | Defensive allocation |

**Important:** TSETMC equity and ETF quotations are normally in **rials**, but
our portfolio's starting capital is specified in **toman**. Return ratios are
dimensionless; we do not divide rials by toman or infer an actual share count.
Results show portfolio wealth in toman after applying dimensionless returns.

## Data and provenance

**Live data:** `pytse-client` 0.19.1 downloads adjusted `close` history and
trading volume for the six instruments, and a direct public TSETMC index JSON
endpoint supplies the broad-market index history. Data are normalized to
Gregorian dates. Per-symbol CSVs and sidecar JSON records are cached to disk
and reused when fresh. `--cache-only` permits a strictly offline replay of
previously retrieved live histories. Every run writes a source manifest.

**Public sources / documentation:**

- TSETMC exchange: https://www.tsetmc.com/
- Official exchange index JSON endpoint used here:
  https://cdn.tsetmc.com/api/Index/GetIndexB2History/32097828799138957
- `pytse-client` public repository: https://github.com/Glyphack/pytse-client
- `pytse-client` versioned package: https://pypi.org/project/pytse-client/0.19.1/

**Historical adjustment warning:** Adjusted closes are convenient for
studying historical returns across corporate actions; they are *not*
necessarily executable market prices. Different vendor treatment of dividends,
capital increases, ETF cash distributions, and price gaps can change the
backtest. Compare a sample of adjusted returns against exchange corporate
announcements before treating live-mode results as reliable.

## Mathematical model

For each asset `i` on signal day `t`, the past `M=60` trading-session momentum is:

\[
 m_{i,t}=\frac{P_{i,t}}{P_{i,t-M}}-1
\]

The broad-market index filter is based on its trailing `L=200` session average:

\[
 \bar I_{200,t}=\frac{1}{200}\sum_{j=0}^{199}I_{t-j}
\]

The **last exchange session of each completed Gregorian month** is the decision
point. If the index is higher than its 200-session average, the two stocks with
highest positive 60-session momentum qualify. Up to 50% of capital is split
among the two qualifying stocks (normally 25% each). If only one qualifies,
25% is allocated; if neither qualifies or the market filter fails, the unused
stock sleeve goes to the defensive ETF. Gold receives up to 30% if its own
momentum is positive. The balance is invested in the defensive ETF.

`config/strategy.yml` can optionally use inverse-volatility weights in the
stock sleeve instead of equal weights. The risk model also calculates
annualized realized covariance to inspect diversification. This version has
**no fitted return-prediction ML model**, no data-mined threshold search, and
no guarantee of positive results.

### Important execution timeline

1. Close of day **D**: observe prices and construct monthly decision.
2. Close of the **next actual exchange session, D+1**: simulate requested trades,
   using adjusted closes as an approximation for execution prices. If an asset
   has no newly observed quotation with positive volume, the backtester aborts
   the rebalance in strict mode (or skips it if strict mode is disabled).
3. During **D+2**: the new positions earn returns; never use today's signal to
   earn an already completed return on the same day.

Realized asset weights drift between monthly executions. The simulator
accounts for buys, sells, transaction fees on both sides, and cash before
initial deployment. It never buys or sells an asset simply because the last
available close was forward-filled during a trading suspension.

### Metrics

- `total_return`, `cagr`, `annualized_volatility`
- `sharpe_zero_rf`: assumes zero risk-free return (an educational simplification)
- `max_drawdown`: worst peak-to-trough fall in normalized portfolio wealth
- TEDPIX comparison on the same modeled calendar and start date
- Detailed asset holdings, order history, data-quality and quote-availability log

## Generated reports

| File | What you can inspect |
|---|---|
| `RESEARCH_REPORT.md` | Executive overview, metrics, target, methodology limitations |
| `performance_and_drawdowns.png` | Strategy vs index and drawdowns |
| `daily_performance.csv` | Capital, returns, fees, benchmark, stale held assets |
| `daily_holdings.csv` | All post-close invested weights, including accounting cash |
| `monthly_decisions.csv` | Signal date, following execution date, selected stocks, intended targets |
| `trades.csv` | Simulated buy/sell events, amounts, dates |
| `performance_metrics.csv` | Comparison metrics, net of trading costs |
| `annualized_covariance.csv` | Annualized empirical covariance estimate |
| `data_quality.csv` | Missing quotes, coverage, first/last observable dates |
| `quotation_observed.csv` | For each day and asset, whether an executable quotation was observed |
| `last_target_weights.csv` | Latest completed-month model target, NOT a live trade instruction |
| `run_manifest.json` | Data mode, provider provenance, fetch times, documented limitations |

## How to customize the research

In `config/strategy.yml`, change:

- `start_date` and `end_date` (Gregorian YYYY-MM-DD, null end means latest)
- stock symbols or the list of equity candidates
- `momentum_sessions` (60), `trend_sessions` (200), `risk_sessions` (60)
- `equity_sleeve` (0.50) and `gold_sleeve` (0.30)
- `stock_weighting` (`equal` or `inverse_vol`)
- `cost_bps_per_side` (15 basis points in this **assumed** fee model)

After a universe or method change, use `--refresh` so quotes aren't confused
with a previous set under the same ID. Strict execution is recommended; setting
`strict_execution: false` **skips** any infeasible rebalance rather than
fabricating a trade.

## Limitations and next research steps

This is a **research-grade learning prototype**, not a live-trading system.
In particular:

1. Closing prices and exchange limits do not ensure that an order could fill.
   Iranian trading halts, limited price ranges, sell queues, minimum lot sizes,
   stamp duty, bid-ask spread and liquidity can materially affect execution.
2. A halted security is indicatively marked at its last observed quotation.
   Stale-valuation days are counted; this is not a true executable portfolio.
3. A present-day, fixed list of assets over past years introduces **selection
   and survivorship bias**. A serious study must use a point-in-time universe.
4. An adjusted history reconstructed today can reflect later corporate-action
   information; this needs point-in-time verification for rigorous backtesting.
5. Inflation, USD/IRR variation and after-inflation *real returns* are omitted;
   this matters significantly in Iran.
6. The TSETMC index benchmark may use a different return construction than
   the adjusted fund/stock histories. Validate like-for-like returns.
7. A convincing research study needs rolling out-of-sample and walk-forward
   analysis, sensitivity to momentum windows, alternative regimes, and a
   realistic execution/slippage model. These are future extensions.

Tests protect the accounting, action lag, tradeability checks, absence of
future price information in early signals, YAML validation, and offline
end-to-end report generation. All values in `outputs/demo/` are **synthetic**.
