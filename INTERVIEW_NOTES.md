# Premialab interview discussion — Tehran research project

## One-minute summary

> I designed a reproducible, modular Python research pipeline for a systematic
> multi-asset portfolio in the Iranian market. It connects publicly available
> Tehran Stock Exchange historical prices, a 60-session momentum ranking,
> a broad-market 200-session trend filter, and a disciplined equity/gold/fixed-
> income allocation. The simulator respects signal publication dates, executes
> only on the next market session, tracks portfolio-weight drift and trading
> costs, and refuses to execute trades when a security has no valid quotation.
> I also added automated tests, dataset provenance and performance reporting.
>
> The offline end-to-end system is tested with deterministic synthetic data;
> actual Iranian-market outcomes still require reliable public-source access
> and further data-quality and execution validation.

## Mathematical formulation

- Stock momentum: `P[t] / P[t-60] - 1`.
- Market regime: `TEDPIX[t] > mean(TEDPIX[t-199:t])`.
- Candidate ranking: highest **positive** momentum among four equities.
- Allocation: up to 50% in two equities, 30% in a gold ETF when its momentum is
  positive, with all unallocated exposure in a fixed-income ETF.
- Risk model: annualized sample volatility and covariance based on a rolling
  60-session window. Optional inverse-vol weighting is implemented.
- Execution: close-of-day signal at `D`, simulated trade at `D+1` close,
  new portfolio exposure earns returns from `D+1` to `D+2`.
- Measurement: net performance, compound return, realized volatility,
  zero-risk-free Sharpe, and maximum drawdown, compared with the market index.

## Software design highlights

- Small, separable Python modules with explicit input and output contracts.
- YAML configuration with validated asset IDs and percentage constraints.
- Public-source ingestion with cache and dated provenance; no fake live fallback.
- Real quotes distinguished from stale last-known prices.
- Post-trade portfolio weights, drift, transaction fee deductions, and audit log.
- Unit and integration tests, reproducible seed for the **synthetic** scenario.

## The difficult research problem

The challenge is less about computing the momentum formula than about obtaining
credible financial data and ensuring *backtest executability*. Iranian stocks
can be halted or price-limited, so yesterday's quotation may not be a price at
which an order could actually fill. Similarly, current-vintage adjusted price
histories may differ from data available in the past. A model can look excellent
while failing in reality if these issues are ignored.

## What has **not** been demonstrated

No verified live Iranian-market backtest performance is claimed. The synthetic
figures in `outputs/demo/` only test the code path. Future steps would include
market-microstructure fill modeling, out-of-sample parameter selection, dynamic
universe construction, price adjustment auditing, and inflation-adjusted returns.
