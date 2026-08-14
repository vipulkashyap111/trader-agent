# Known-liquidity map

Verified options-liquidity classification for tickers we track. Update dates are the last time `scripts/research.py check-spread` or the ATM liquidity row was checked on the 3rd-Friday monthly.

Liquidity class definitions:
- **TRADEABLE** — ATM primary-monthly spread ≤ 1%, OI ≥ 500 for both call and put ATM. Vertical spreads and CSPs both viable.
- **MARGINAL** — ATM spread 1-3%, OI ≥ 500. Vertical spreads only with limit orders and smaller size. Explicit user override needed.
- **STOCK-ONLY** — ATM spread > 3% OR OI < 500 on the monthly. Do not attempt options; use shares.
- **UNTESTED** — Not verified recently; run research first.

## Current classification

| Ticker | Class | Last verified | ATM spread (monthly) | ATM OI | Notes |
|---|---|---|---|---|---|
| NVDA | MARGINAL | 2026-08-14 | 1.38% | 44,157 | Best options liquidity in the personal universe. Sep 18 gate closed at 1.38%; earnings can push it wider. |
| GOOGL | MARGINAL | 2026-08-14 | 1.55% | 5,028 | Second-best. Monthly usually 1-2%. |
| AMD | MARGINAL | 2026-08-14 | 2.22% | 1,473 | Was 2.7% in July; watch for further deterioration. |
| MU | STOCK-ONLY | 2026-08-14 | 3.04% | 2,307 | Right at 3% boundary. Volatile. |
| MSFT | STOCK-ONLY | 2026-08-14 | 3.63% | 1,429 | Surprisingly illiquid ATM for a mega-cap. Verified across 3 sessions. |
| RDDT | STOCK-ONLY | 2026-08-14 | 3.88% (best case) | 928 | Structurally illiquid on ALL expiries. Even Sep monthly FAILs. Stock-only permanent classification unless something changes. |
| SMH | STOCK-ONLY | 2026-08-14 | 6.27% | 241 | ETF but bad options. Use for regime read, trade via shares. |
| WDC | STOCK-ONLY | 2026-08-14 | 6.10% | 72 | Consistently bad. |

## Structurally-illiquid stocks (permanent stock-only)

- **RDDT** — verified 6/25, 7/06, 7/15, 8/14. All expiries FAIL. Even ATM straddles have 5%+ spread.
- **WDC** — verified 6/26, 7/15, 8/14. OI < 100 on ATM. Never tradeable.

## Update protocol

1. When a `research <TICKER>` output shows a new ATM spread reading, update this table.
2. Downgrade a ticker's class only after 2+ consecutive sessions confirm.
3. If a STOCK-ONLY ticker prints TRADEABLE unexpectedly, run `check-spread` on 2 non-ATM strikes before believing it.

## Universe implication

**The Tier-1 "liquid options" hypothesis is wrong for the personal universe.** Only NVDA / GOOGL / AMD sit near MARGINAL; everything else is STOCK-ONLY on monthlies. Plan setups accordingly — do not default to spreads for tickers not on the MARGINAL row.
