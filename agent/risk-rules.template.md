# Risk Rules — TEMPLATE

> ⚠️ This is a **template**. Do not put your real numbers here. The install script renders this template into `{LOCAL_DATA_PATH}/risk-rules.md` with your actual values. The agent reads from the local file, not from this template.

## Account
- `ACCOUNT_SIZE_USD`: {{ACCOUNT_SIZE_USD}}
- `RISK_PCT_PER_TRADE`: {{RISK_PCT_PER_TRADE}}
- `MAX_HEAT_PCT`: {{MAX_HEAT_PCT}}

## Derived (computed by install script)
- `MAX_RISK_USD` = `ACCOUNT_SIZE_USD` × `RISK_PCT_PER_TRADE` / 100 = {{MAX_RISK_USD}}
- `MAX_HEAT_USD` = `ACCOUNT_SIZE_USD` × `MAX_HEAT_PCT` / 100 = {{MAX_HEAT_USD}}

## Hard limits
- No single trade may risk more than `MAX_RISK_USD`
- Total open risk across all positions may not exceed `MAX_HEAT_USD`
- Maximum concurrent open positions: {{MAX_OPEN_POSITIONS}}

## Sector / instrument focus
- Sectors: {{SECTORS}}
- Instruments: {{INSTRUMENTS}}
- Horizons: {{HORIZONS}}

## Behavioral rules
- After 2 consecutive stop-outs in the same week: **24h trading cooldown**
- No new positions in the 30 minutes before market close (Friday: 60 minutes)
- No new positions during FOMC press conference window or 30 min after CPI release
- No earnings-window positions unless strategy is explicitly event-driven (see playbook J/K)

## Options-specific
- No naked short calls — ever
- Defined-risk only for short-premium unless strike represents a price you would happily own
- Close short-premium at 21 DTE or 50% max profit, whichever first
- Spread width such that max loss per spread ≤ `MAX_RISK_USD`

## Review cadence
- Daily mark-to-market via `@trader portfolio`
- Weekly aggregate via `@trader weekly`
- Strategy graduation: ≥20 paper trades with positive expectancy before going live
- Quarterly strategy re-validation (markets regime-shift)
