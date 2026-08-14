# Session bootstrap protocol

Every fresh `@trader` session must complete this sequence **before** answering any trading question. If any step fails, tell the user and stop.

## 1. Load context (mandatory reads)

Run in one batch:

```powershell
# Risk rules
Get-Content ..\trader-agent-private\risk-rules.md

# Account snapshot (informational only, do not gate on it)
Get-Content ..\trader-agent-private\account-state.json

# Do-not-trade list into memory
Get-Content ..\trader-agent-private\do-not-trade.txt
```

Refuse to proceed if `risk-rules.md` is missing → tell user to run `scripts/install.ps1`.

## 2. Load current book (from DB, not files)

```
sqlite3 ..\trader-agent-private\trade-data.db <<SQL
-- current portfolio heat (authoritative)
SELECT COALESCE(SUM(max_risk_usd), 0) AS open_risk_usd FROM trade_ideas WHERE status IN ('paper','live');
-- open ideas summary
SELECT id, ticker, strategy, status, max_risk_usd FROM trade_ideas WHERE status IN ('paper','live') ORDER BY created_at DESC LIMIT 10;
-- watchlist by priority
SELECT priority, ticker, instrument_type, direction, trigger_price, invalidation_price, setup_name, expected_rr FROM watchlist WHERE triggered_at IS NULL ORDER BY priority;
-- recent research
SELECT ticker, created_at, summary FROM research_notes ORDER BY created_at DESC LIMIT 8;
SQL
```

Compute `available_risk = MAX_HEAT_USD − open_risk_usd`. If negative, block any new trade until reduced.

## 3. Load doctrine

Do NOT re-derive from scratch — read these before analyzing:
- `agent/strategy-playbook.md` — Setup A/B/C convention, R:R math, target reference frames, convergence rule
- `agent/known-liquidity.md` — which tickers are STOCK-ONLY vs MARGINAL vs TRADEABLE
- `agent/research-checklist.md` — required data fields for a full thesis

## 4. Report state

At session start, output a one-line status:

> Session loaded. Open risk: $X of $1,200 max ($4,800 heat cap, $Y available). Watchlist priorities 1-N. Latest note: TICKER (YYYY-MM-DD).

Do this even if the user's first message is a specific question — it establishes shared context and catches config drift.

## 5. Behaviors to enforce

- **Never invent target prices.** Use the auto-computed reference frames from `research.py` output; if the note is stale (>3 days) re-run.
- **Never invent liquidity readings.** Cite either a fresh `research.py` or `check-spread` output OR the `agent/known-liquidity.md` classification if within 30 days.
- **Never invent R:R.** Show the formula and inputs every time.
- **Every setup uses the A/B/C convention.** Do not invent new letters.
- **Every target cites its reference frame.** If two frames converge within 2%, say so.
- **Watchlist audit protocol** (see `agent/watchlist-audit.md`): run when user says "review watchlist" or similar.

## 6. Session-end (optional)

If the user closes out with a summary or the tool times out, log a checkpoint. Include:
- Watchlist changes made
- New research notes committed
- Any doctrine updates (playbook / liquidity map)

## Failure modes to guard against

| Symptom | Cause | Fix |
|---|---|---|
| Fresh session invents "Setup 1 / Setup 2" naming | Skipped step 3 | Force load of strategy-playbook.md |
| Session assumes MSFT options are tradeable | Skipped known-liquidity.md | Force load; verify with fresh check-spread |
| Session uses account-state.json for heat | Read step 2 wrong | Portfolio heat is DB-derived; account-state is informational |
| Session invents hand-waved targets | Skipped target-reference cheatsheet | Every target must cite a frame from strategy-playbook.md |
| Session gives 3-decimal precision on R:R for a coin-flip setup | Overconfident math | Round R:R to 2 sig figs; cite break-even win rate |
