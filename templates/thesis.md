# Thesis: {{TICKER}} — {{STRATEGY}}

**Date:** {{DATE}}
**Research note:** `{{NOTE_PATH}}`

## Thesis
*(1 sentence)*

## Setup
- **Horizon:** swing | position
- **Strategy:** *(reference strategy-playbook.md entry)*
- **Entry trigger:**
- **Target:**
- **Stop:**
- **Time stop:**
- **Invalidation:**

## Position sizing
> Local file only — do NOT echo dollars into chat unless user asks.
- Instrument:
- Sizing formula used: *(see agent prompt "Position sizing math")*
- Inputs: entry=$X, stop=$Y (or premium=$P, width=$W, credit=$C as applicable)
- **Computed size:** N shares / contracts
- Risk on this trade: $Y  (must be ≤ MAX_RISK_USD)
- Risk as % of account:
- Risk as R-multiple = 1R (by definition)

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
