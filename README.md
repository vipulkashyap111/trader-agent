# trader-agent

A Copilot CLI custom agent for **disciplined, data-driven research and journaling** of stock and options trade ideas. The agent gathers data, builds structured theses, enforces risk rules, and maintains a trade journal — but **never executes trades**. All decisions remain with the human.

## ⚠️ Disclaimer

**NOT FINANCIAL ADVICE.** This is a research and journaling tool. The agent does not execute trades and does not predict markets. All decisions are yours. **You can lose money — including more than you invest** if you trade options. Past performance does not predict future results. Read the agent's output critically and red-team every thesis. The author and contributors accept no liability for your trading outcomes.

## Philosophy

1. **Data → thesis → plan → size → execute → journal.** Never skip steps.
2. **Paper-trade every new strategy ≥20 times** before going live.
3. **Pre-define exit rules** (target, stop, time stop, invalidation) BEFORE entry.
4. **Risk per trade is a hard cap.** Position size derives from stop distance, not gut feel.
5. **The agent is an analyst, not a decision-maker.** It gathers, summarizes, red-teams. You decide.
6. **Every idea is logged.** Outcomes feed back into pattern recognition.

## What's in this repo

| Path | Purpose |
|------|---------|
| `agent/trader.agent.md` | Copilot CLI agent definition |
| `agent/research-checklist.md` | The data-gathering checklist the agent must complete before any thesis |
| `agent/strategy-playbook.md` | Common option/stock setups with entry/exit templates |
| `agent/risk-rules.template.md` | Template — your real numbers go in a private file, not here |
| `schema/init.sql` | SQLite schema for the local trade DB |
| `templates/` | Markdown templates for research notes, theses, trade logs |
| `examples/` | Sanitized sample outputs |
| `scripts/install.ps1` | One-time setup: renders template with your numbers, creates DB, installs agent |
| `scripts/verify-mcp.ps1` | Smoke-tests the MCP connections |

## What's **not** in this repo (intentionally)

- Your actual account size, risk amounts, or position sizes
- Your watchlist or do-not-trade list
- Any trade ideas, journal entries, or P&L data
- MCP credentials (FRED API key, etc.)

All personal data lives in a sibling folder (default: `..\trader-agent-private\`) which **must not** be committed to a public repo.

## MCP servers used

| Server | Purpose | Install |
|--------|---------|---------|
| `mcp-yahoo-finance` | Quotes, history, options chains, fundamentals, news | `uvx mcp-yahoo-finance` |
| `sec-edgar-mcp` | 10-K/Q filings, insider Form 4 | `uvx --from git+https://github.com/stefanoamorelli/sec-edgar-mcp.git sec-edgar-mcp` |
| `mcp-fred` | Macro data (rates, CPI, DXY, VIX) | `uvx mcp-fred` — requires free FRED API key |

⚠️ **All three are community-maintained.** Review their source before running. Yahoo's API is unofficial and may break. SEC EDGAR requires a User-Agent string identifying you (per SEC policy).

## Quick start

```powershell
# 1. Clone this repo
git clone <your-repo-url> trader-agent
cd trader-agent

# 2. Install MCP servers (one-time)
# Make sure uv/uvx is installed: https://docs.astral.sh/uv/
uvx --help

# 3. Run the install script — prompts for your account size, risk %, paths
.\scripts\install.ps1

# 4. Verify MCPs respond
.\scripts\verify-mcp.ps1

# 5. In Copilot CLI:
@trader research NVDA
```

## Updating risk rules

Edit `..\trader-agent-private\risk-rules.md` directly. The agent reads it on each invocation. **Never** edit `agent/risk-rules.template.md` with your real numbers — it's committed.

## License

MIT — see [LICENSE](LICENSE).
