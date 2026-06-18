# Strategy Playbook

Reference catalog of stock and options setups suitable for **swing (days–weeks)** and **position (months)** horizons. Each entry includes when it fits, structure, and default exits. Adapt — do not copy blindly.

## Stock strategies

### A. Trend continuation (swing)
**When:** Price above rising 20/50 SMA, pullback to 20 SMA with shallow retrace (<38.2% Fib of prior leg), sector ETF trending up.
**Structure:** Long shares.
**Entry:** Break above prior day's high after pullback.
**Stop:** Below the pullback low or 1.5× ATR(14), whichever is tighter.
**Target:** Prior swing high, then trail 20 SMA.
**Time stop:** Exit if no progress in 10 sessions.

### B. Breakout from base (swing/position)
**When:** 6+ weeks of consolidation, decreasing volume into the base, RS line at new highs, fundamentals confirmed.
**Structure:** Long shares.
**Entry:** Volume-confirmed breakout above pivot (>1.5× avg volume).
**Stop:** Below pivot or 7-8% below entry, whichever is tighter.
**Target:** Measured move (base depth projected upward). Sell partial at 20%, trail rest.
**Time stop:** Exit if breakout fails within 3 sessions.

### C. Mean reversion (swing)
**When:** Strong stock pulled back to support, RSI(2) < 10, VIX not spiking, no negative news.
**Structure:** Long shares.
**Entry:** Reversal candle (hammer, engulfing) at support.
**Stop:** Below support by 1× ATR.
**Target:** Return to 20 SMA.
**Time stop:** 5 sessions max.

## Long-premium options strategies

### D. Long call (directional swing/position)
**When:** Strong directional view, IV rank < 40 (premium not expensive), 30-90 DTE.
**Structure:** Buy ATM or 1 strike OTM call.
**Entry:** With the underlying signal (B or A above).
**Stop:** 50% loss of premium OR underlying breaks the technical stop.
**Target:** 100% gain on premium OR underlying target.
**Time stop:** Exit at 21 DTE regardless to avoid gamma/theta acceleration.
**Risk:** Premium paid = max loss. Size so premium ≤ MAX_RISK_USD.

### E. Long put (bearish swing)
Mirror of D. Beware: indices/major tech often grind up; long puts have low expectancy outside clear distribution patterns.

### F. Long call vertical / debit spread (defined directional)
**When:** Directional view but IV rank 40-70, want to cap cost.
**Structure:** Buy ATM call, sell OTM call (width = expected move).
**Max loss:** Debit paid.
**Max gain:** Width − debit.
**Exit:** 50% of max gain OR underlying invalidation.
**Use:** When pure long call too expensive.

## Short-premium options strategies

### G. Short put (cash-secured, willing to own)
**When:** Want to own the stock at a lower price, IV rank > 50, strong fundamentals.
**Structure:** Sell put at strike where you'd be happy to own. 30-45 DTE.
**Risk:** Assignment at strike − premium received.
**Exit:** 50% of max profit OR 21 DTE OR underlying breaks key support.
**Position size:** (strike × 100) − premium received ≤ available capital × allocation %.

### H. Bull put credit spread (defined risk)
**When:** Bullish or neutral view, IV rank > 50, defined risk preferred over short put.
**Structure:** Sell put, buy further-OTM put (width = max risk per spread).
**Max loss:** Width − credit received.
**Max gain:** Credit received.
**Exit:** 50% of max profit OR 21 DTE OR short strike breached.
**Position size:** (width − credit) × contracts × 100 ≤ MAX_RISK_USD.

### I. Iron condor (range-bound)
**When:** Expecting range, IV rank > 60, no near-term catalyst, 30-45 DTE.
**Structure:** Sell OTM put spread + sell OTM call spread. Strikes at ~1 SD.
**Exit:** 25-50% of max profit OR 21 DTE OR either short strike tested.
**Use sparingly:** Tech names often trend; iron condors get tested.

## Earnings strategies

### J. Pre-earnings IV expansion (long premium)
**When:** IV rank < 40 weeks before earnings, expecting IV to rise into the print.
**Structure:** Long calendar or long straddle.
**Exit:** Close BEFORE earnings announcement — never hold through binary unless that is explicitly the thesis.

### K. Post-earnings IV crush (short premium)
**When:** Only after the event, when implied move was overstated. Requires very strong fundamentals view post-print.
**Structure:** Short strangle or iron condor.
**Caveat:** High-skill, high-risk. Default: avoid.

## Anti-patterns (do not trade)

- Naked short calls (undefined risk, never in a personal account)
- Earnings lottery tickets (buying OTM options the day before earnings hoping for a moonshot)
- Adding to losers without a thesis change
- Pyramiding on a thesis you have not re-validated
- "Cheap" far-OTM options as primary directional bet — almost always negative EV
- Trading the same idea repeatedly after stop-outs ("revenge trading")
