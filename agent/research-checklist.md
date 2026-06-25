# Research Checklist

Complete **every** section before producing a thesis. Mark items "unknown" or "data unavailable" rather than skipping. Cite source for each fact.

## 1. Snapshot
- Current price (Yahoo)
- Market cap, sector, industry
- Float, short interest %, days to cover
- Average daily volume (30d)
- 52-week high/low, distance from each

## 2. Fundamentals
- Last 4 quarters: revenue, EPS, surprise % vs estimate
- Revenue growth YoY trend (accelerating/decelerating)
- Forward P/E vs sector median
- Gross margin trend
- Free cash flow (TTM)
- Debt/equity, cash on balance sheet
- Insider transactions last 90 days (SEC EDGAR Form 4): net buy/sell, notable names
- Latest 10-Q: top 3 risk factors summarized

## 3. Technicals
**Daily, 1-year lookback:**
- Trend: 20 SMA vs 50 SMA vs 200 SMA alignment
- ATR(14) — current and as % of price
- 30-day realized volatility
- Key horizontal support and resistance levels (last 6 months)
- Recent gaps (filled or unfilled)
- Volume profile: any anomalies (e.g., distribution days, accumulation)

**Intraday context (hourly, 60-day):**
- Short-term trend
- Pre/post-market activity if relevant

## 4. Options (if the thesis involves options)
- **30-day ATM IV** (interpolated from nearby expiries — NOT the nearest expiry, which is noisy at 0-DTE)
- IV rank (current IV vs 1-year range) — if not available from yfinance, note as data gap
- IV vs HV (30-day): rich, fair, or cheap
- Term structure of IV: contango or backwardation
- 25-delta skew (put IV minus call IV)
- Open interest concentration (top 3 strikes/expirations, calls and puts)
- **Expected move (next 30d) from ATM straddle price** — straddle ÷ stock_price
- Days to next earnings (avoid pinning trades to earnings unless event-driven)
- **Liquidity check on the strikes you would actually trade:**
  - Bid/ask spread ≤ 1% of mid → PASS, else FAIL
  - Open interest ≥ 500 contracts → PASS, else FAIL
  - The research note's "Tradeable strike zone" section shows the range of strikes that pass on the primary expiry — use it to pre-screen
  - **For vertical spreads:** the `check-spread` CLI subcommand verifies both legs and computes the estimated net debit/credit at mid. **Required gate before sizing any spread.**
  - **Standard-monthly expiries (3rd Friday) almost always have better liquidity than weeklies.** The script flags this on the primary expiry; prefer monthlies for any multi-week position.

## 5. Catalysts and sentiment
- Next earnings date (confirmed or estimated)
- **Earnings move history** — avg ABS % move on the last 8 earnings prints, up/down split. Sets baseline expectation for the next print and informs whether the implied move is rich or cheap.
- Other known catalysts (product launch, FDA, conference, lockup expiry)
- News last 7 days: sentiment (positive/neutral/negative), materiality (high/medium/low). Cite headlines.
- Analyst rating changes last 30 days: upgrades/downgrades, price target revisions
- Social sentiment if available (note: low signal, treat as contrarian indicator at extremes)

## 6. Macro context
- SPY trend (20/50/200 SMA)
- QQQ trend (relevant for tech)
- VIX level and trend
- 10Y Treasury yield level and trend (FRED: DGS10)
- DXY level and trend (FRED: DTWEXBGS)
- **Relative strength of the ticker vs sector ETF and SPY over 21d and 63d** — concrete % difference, not vague "outperforming". The `scripts/research.py` helper computes this. RS turning negative is often the earliest sign of a regime change.
- Fed meeting / CPI / NFP within next 7 days

## 7. Data gaps
Explicitly list anything that was unavailable, stale, or required estimation. The thesis must acknowledge these.

## 8. Sources
List every URL, MCP call, and data timestamp used.
