# Thesis: {{TICKER}} — {{STRATEGY}}

**Date:** {{DATE}}
**Research note:** `{{NOTE_PATH}}`

## Thesis
*(1 sentence)*

## Instrument
- **Type:** stock | options *(pick exactly one — sizing math differs)*
- **If options:** structure = long_call | long_put | bull_call_debit | bear_put_debit | credit_spread | iron_condor | csp | calendar
- **Liquidity verified?** `python scripts/research.py check-spread ...` output pasted below if options:
  ```
  (paste check-spread verdict here, must be PASS or MARGINAL)
  ```

## Setup
- **Horizon:** swing | position
- **Strategy:** *(reference strategy-playbook.md entry)*
- **Entry trigger:**
- **Target:**
- **Stop:**
- **Time stop:**
- **Invalidation:**

## Position sizing — STOCK
> Fill ONLY if Instrument.Type = stock
- Entry: $___
- Stop: $___
- Risk/share = entry − stop = $___
- **Shares = floor(MAX_RISK_USD / risk_per_share) = ___**
- Notional = shares × entry = $___  (___% of $20k new-trades budget)
- Risk on this trade: $___ (must be ≤ $1,200)

## Position sizing — OPTIONS
> Fill ONLY if Instrument.Type = options
- Structure: ___
- Per-contract risk (max loss): $___
- **Contracts = floor(MAX_RISK_USD / per_contract_risk) = ___**
- For CSP only: gap-adjusted risk = (strike − mental_stop) × gap_multiplier × 100 − premium  (gap_multiplier = 2× or 3× if earnings inside DTE)
- Premium / debit / credit: $___
- Risk on this trade: $___ (must be ≤ $1,200)
- R:R = (target_value − entry_value) / risk = ___ : 1  (must be ≥ 1.5 : 1 absent explicit override)

## Expected value (rough)
> Local file only — chat output uses R-multiples.
- P(win) × win_R = +A R
- P(loss) × loss_R = −B R
- **EV ≈ (A − B) R**
- Conviction (1–5):

## Top 3 ways I am wrong
1.
2.
3.

## Rule check
- [ ] Risk on this trade ≤ MAX_RISK_USD
- [ ] Total heat after entry ≤ MAX_HEAT_USD
- [ ] Open positions count ≤ MAX_OPEN_POSITIONS
- [ ] No earnings within 7 days (or strategy is event-driven)
- [ ] Liquidity OK (spread ≤ 1% mid for options; avg vol ≥ 500k for stock)
- [ ] Ticker not on do-not-trade list
- [ ] Correlation with open positions ≤ 0.7
- [ ] Behavioral rules satisfied (no cooldown, no FOMC window)

## Decision
**Status:** idea | ready-for-paper | blocked
**Block reason (if any):**

## Next action
- *(e.g., wait for entry trigger, run review, log as paper)*
