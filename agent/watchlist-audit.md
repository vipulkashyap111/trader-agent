# Watchlist audit protocol

Triggered by user phrases: "review watchlist", "review my watchlist stocks", "audit watchlist", "check open setups", "how's the watchlist".

## Steps

1. **Load watchlist**:
   ```sql
   SELECT priority, ticker, instrument_type, direction, trigger_price, invalidation_price, setup_name, expected_rr, notes
   FROM watchlist WHERE triggered_at IS NULL ORDER BY priority;
   ```

2. **Run `scripts/research.py` in parallel** for every ticker (use `ForEach-Object -Parallel -ThrottleLimit 4`).

3. **For each ticker, produce a triage row**:

   | Ticker | Price | Trigger | Status | Action |
   |---|---|---|---|---|
   | Where status ∈ {DEAD (thesis invalidated), IN-ZONE (trigger fired, evaluate now), APPROACHING (within 1 ATR of trigger), NOT-YET (far from trigger), BROKEN (invalidation price hit)} |

4. **Detail the actionable ones only** (IN-ZONE and DEAD):
   - For IN-ZONE: full A/B/C setup menu with R:R math, target-reference frames, sizing example
   - For DEAD: state which invalidation hit, propose new watchlist row (flipped direction, new trigger, new invalidation) OR delete

5. **Consolidated recommendations block** at the end:
   - Which watchlist rows to UPDATE (priority, direction, trigger, invalidation, setup)
   - Which to DELETE (thesis dead, no reactivation path)
   - Which to KEEP as-is
   - Best fresh setup in the basket (highest R:R that is currently entry-ready)

6. **Ask** before executing DB changes. Auto-apply only in autopilot mode.

## Guardrails

- **Do not chase a stale trigger.** If price is 5%+ past the trigger, the setup is no longer "in-zone" — mark it "extended" and consider a pullback re-entry (Setup B recompute).
- **Do not resurrect a broken thesis silently.** If a bear thesis got invalidated by a rally, the follow-up is "delete OR flip to bull with new triggers" — never "keep watching for a lower low that may never come".
- **Rank by R:R, not by conviction.** The audit output orders actionable ideas by R:R descending.
- **Track macro regime.** Prepend the review with 21d RS of SMH/QQQ/SPY. Sector rotation kills stale sector-specific theses first.

## Retrospective triggers

When auditing surfaces a thesis outcome (fired + hit target, fired + stopped, never triggered + expired), create a retrospective from `templates/retrospective.md` in `..\trader-agent-private\notes\retrospectives\`.

## Output format

Always finish the audit with:

> **Watchlist deltas to apply:** [list]
> **Best fresh setup right now:** TICKER Setup [B/C/D] at $X, target $Y, stop $Z, R:R n.n:1
> **Awaiting alerts on:** [tickers with APPROACHING or NOT-YET status]

This preserves session-to-session state.
