"""
trader-agent quote helper.

Fast, deterministic replacement for the yahoo-finance MCP when it's unavailable.
Covers the data gaps we've hit: option chains + greeks + IV, earnings dates,
dividends/ex-div, and news headlines.

Usage:
    python scripts/quote.py MSFT                          # price snapshot
    python scripts/quote.py MSFT --options 2026-08-21     # full option chain
    python scripts/quote.py MSFT --options 2026-08-21 --strike 440 --right call
    python scripts/quote.py MSFT --earnings               # next + history
    python scripts/quote.py MSFT --divs                   # dividend history + ex-div
    python scripts/quote.py MSFT --news                   # recent headlines
    python scripts/quote.py MSFT --all                    # everything

Add --json for machine-readable output.

Requires: yfinance, pandas.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import math
import sys
from typing import Any

import pandas as pd
import yfinance as yf

# Force UTF-8 stdout on Windows so tables and em-dashes render correctly.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _safe(v: Any) -> Any:
    if v is None:
        return None
    try:
        if hasattr(v, "item"):
            v = v.item()
    except Exception:
        pass
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _fmt_pct(x: float | None) -> str:
    return f"{x:+.2f}%" if x is not None else "n/a"


def _fmt_price(x: float | None, digits: int = 2) -> str:
    return f"${x:,.{digits}f}" if x is not None else "n/a"


def get_price_snapshot(ticker: yf.Ticker) -> dict:
    info = ticker.fast_info
    hist = ticker.history(period="10d", auto_adjust=False)

    last = _safe(info.get("last_price"))
    prev = _safe(info.get("previous_close"))
    day_low = _safe(info.get("day_low"))
    day_high = _safe(info.get("day_high"))
    vol = _safe(info.get("last_volume"))
    yr_low = _safe(info.get("year_low"))
    yr_high = _safe(info.get("year_high"))

    chg = (last - prev) if (last and prev) else None
    chg_pct = (chg / prev * 100) if (chg is not None and prev) else None

    ohlcv = []
    if not hist.empty:
        for idx, row in hist.tail(5).iterrows():
            ohlcv.append({
                "date": idx.strftime("%Y-%m-%d"),
                "open": _safe(row.get("Open")),
                "high": _safe(row.get("High")),
                "low": _safe(row.get("Low")),
                "close": _safe(row.get("Close")),
                "volume": _safe(row.get("Volume")),
            })

    return {
        "symbol": ticker.ticker,
        "last": last,
        "prev_close": prev,
        "change": chg,
        "change_pct": chg_pct,
        "day_range": {"low": day_low, "high": day_high},
        "year_range": {"low": yr_low, "high": yr_high},
        "volume": vol,
        "recent_ohlcv": ohlcv,
    }


def get_option_chain(ticker: yf.Ticker, expiry: str, strike: float | None = None,
                     right: str | None = None) -> dict:
    if expiry not in ticker.options:
        return {"error": f"Expiry {expiry} not available. Available: {list(ticker.options)[:10]}"}

    chain = ticker.option_chain(expiry)
    result = {"expiry": expiry, "calls": [], "puts": []}

    def _row_to_dict(row):
        return {
            "strike": _safe(row["strike"]),
            "last": _safe(row.get("lastPrice")),
            "bid": _safe(row.get("bid")),
            "ask": _safe(row.get("ask")),
            "mid": _safe((row.get("bid", 0) + row.get("ask", 0)) / 2) if row.get("bid") and row.get("ask") else None,
            "volume": _safe(row.get("volume")),
            "open_interest": _safe(row.get("openInterest")),
            "iv": _safe(row.get("impliedVolatility")),
            "itm": bool(row.get("inTheMoney", False)),
        }

    calls_df = chain.calls
    puts_df = chain.puts

    if strike is not None:
        calls_df = calls_df[abs(calls_df["strike"] - strike) < 0.01]
        puts_df = puts_df[abs(puts_df["strike"] - strike) < 0.01]

    if right in (None, "call", "c"):
        result["calls"] = [_row_to_dict(r) for _, r in calls_df.iterrows()]
    if right in (None, "put", "p"):
        result["puts"] = [_row_to_dict(r) for _, r in puts_df.iterrows()]

    return result


def list_expiries(ticker: yf.Ticker) -> list[str]:
    return list(ticker.options)


def get_earnings(ticker: yf.Ticker) -> dict:
    out: dict[str, Any] = {"next": None, "history": []}
    try:
        cal = ticker.calendar
        if isinstance(cal, dict) and cal.get("Earnings Date"):
            dates = cal["Earnings Date"]
            out["next"] = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in dates]
        elif isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.index:
            out["next"] = str(cal.loc["Earnings Date"].iloc[0])
    except Exception as e:
        out["calendar_error"] = str(e)

    try:
        edates = ticker.earnings_dates
        if edates is not None and not edates.empty:
            recent = edates.head(8)
            for idx, row in recent.iterrows():
                out["history"].append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "eps_estimate": _safe(row.get("EPS Estimate")),
                    "eps_reported": _safe(row.get("Reported EPS")),
                    "surprise_pct": _safe(row.get("Surprise(%)")),
                })
    except Exception as e:
        out["history_error"] = str(e)

    return out


def get_dividends(ticker: yf.Ticker) -> dict:
    out: dict[str, Any] = {"next_ex_div": None, "recent": []}
    try:
        info = ticker.info
        exd = info.get("exDividendDate")
        if exd:
            out["next_ex_div"] = dt.datetime.utcfromtimestamp(exd).strftime("%Y-%m-%d")
        out["dividend_rate"] = _safe(info.get("dividendRate"))
        out["dividend_yield"] = _safe(info.get("dividendYield"))
    except Exception as e:
        out["info_error"] = str(e)

    try:
        divs = ticker.dividends
        if divs is not None and not divs.empty:
            for idx, val in divs.tail(6).items():
                out["recent"].append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "amount": _safe(val),
                })
    except Exception as e:
        out["history_error"] = str(e)

    return out


def get_news(ticker: yf.Ticker, limit: int = 10) -> list[dict]:
    try:
        news = ticker.news or []
    except Exception:
        return []
    out = []
    for item in news[:limit]:
        content = item.get("content", item)
        pub = content.get("pubDate") or content.get("providerPublishTime")
        if isinstance(pub, (int, float)):
            pub = dt.datetime.utcfromtimestamp(pub).strftime("%Y-%m-%d %H:%M UTC")
        provider = content.get("provider", {})
        if isinstance(provider, dict):
            provider = provider.get("displayName") or provider.get("name")
        out.append({
            "title": content.get("title"),
            "publisher": provider,
            "published": pub,
            "url": (content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else content.get("link"),
        })
    return out


def render_markdown(symbol: str, data: dict) -> str:
    lines = [f"# {symbol}\n"]

    if "price" in data:
        p = data["price"]
        lines.append("## Price snapshot")
        lines.append(f"- **Last:** {_fmt_price(p['last'])}   "
                     f"Prev close: {_fmt_price(p['prev_close'])}   "
                     f"Change: {_fmt_price(p['change'])} ({_fmt_pct(p['change_pct'])})")
        dr = p["day_range"]
        yr = p["year_range"]
        lines.append(f"- **Day range:** {_fmt_price(dr['low'])} – {_fmt_price(dr['high'])}")
        lines.append(f"- **52w range:** {_fmt_price(yr['low'])} – {_fmt_price(yr['high'])}")
        v = p["volume"]
        lines.append(f"- **Volume:** {v:,}" if v else "- Volume: n/a")
        if p["recent_ohlcv"]:
            lines.append("\n### Recent OHLCV")
            lines.append("| Date | Open | High | Low | Close | Volume |")
            lines.append("|---|---|---|---|---|---|")
            for r in p["recent_ohlcv"]:
                lines.append(f"| {r['date']} | {_fmt_price(r['open'])} | {_fmt_price(r['high'])} | "
                             f"{_fmt_price(r['low'])} | {_fmt_price(r['close'])} | {int(r['volume']):,} |")
        lines.append("")

    if "options" in data:
        o = data["options"]
        lines.append(f"## Options — expiry {o.get('expiry')}")
        if o.get("error"):
            lines.append(f"⚠️ {o['error']}")
        for side in ("calls", "puts"):
            rows = o.get(side, [])
            if not rows:
                continue
            lines.append(f"\n### {side.capitalize()}")
            lines.append("| Strike | Bid | Ask | Mid | Last | Vol | OI | IV | ITM |")
            lines.append("|---|---|---|---|---|---|---|---|---|")
            for r in rows:
                iv_str = f"{r['iv']*100:.1f}%" if r['iv'] else "n/a"
                lines.append(f"| {_fmt_price(r['strike'])} | {_fmt_price(r['bid'])} | "
                             f"{_fmt_price(r['ask'])} | {_fmt_price(r['mid'])} | "
                             f"{_fmt_price(r['last'])} | {r['volume'] or 0} | "
                             f"{r['open_interest'] or 0} | {iv_str} | {'yes' if r['itm'] else ''} |")
        lines.append("")

    if "expiries" in data:
        lines.append("## Available option expiries")
        lines.append(", ".join(data["expiries"][:20]))
        lines.append("")

    if "earnings" in data:
        e = data["earnings"]
        lines.append("## Earnings")
        if e.get("next"):
            lines.append(f"- **Next:** {e['next']}")
        if e.get("history"):
            lines.append("\n### Recent history")
            lines.append("| Date | Est EPS | Reported | Surprise |")
            lines.append("|---|---|---|---|")
            for h in e["history"]:
                lines.append(f"| {h['date']} | {h['eps_estimate']} | {h['eps_reported']} | "
                             f"{_fmt_pct(h['surprise_pct']) if h['surprise_pct'] is not None else 'n/a'} |")
        lines.append("")

    if "dividends" in data:
        d = data["dividends"]
        lines.append("## Dividends")
        lines.append(f"- **Next ex-div:** {d.get('next_ex_div') or 'n/a'}")
        # yfinance returns dividendYield already as a percent (e.g. 0.81 for 0.81%)
        # rather than a fraction, so no *100 needed.
        lines.append(f"- **Annual rate:** {_fmt_price(d.get('dividend_rate'))}   "
                     f"Yield: {_fmt_pct(d.get('dividend_yield'))}")
        if d.get("recent"):
            lines.append("\n### Recent payments")
            lines.append("| Ex-Date | Amount |")
            lines.append("|---|---|")
            for r in d["recent"]:
                lines.append(f"| {r['date']} | {_fmt_price(r['amount'], 3)} |")
        lines.append("")

    if "news" in data:
        lines.append("## News")
        if not data["news"]:
            lines.append("_No news returned._")
        for n in data["news"]:
            lines.append(f"- **{n['published'] or ''}** — {n['title']} _({n['publisher']})_")
            if n.get("url"):
                lines.append(f"  {n['url']}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Quote helper for @trader agent.")
    ap.add_argument("ticker")
    ap.add_argument("--options", metavar="YYYY-MM-DD", help="Fetch option chain for expiry")
    ap.add_argument("--strike", type=float, help="Filter option chain by strike")
    ap.add_argument("--right", choices=["call", "put", "c", "p"], help="Filter by call or put")
    ap.add_argument("--list-expiries", action="store_true", help="List available option expiries")
    ap.add_argument("--earnings", action="store_true")
    ap.add_argument("--divs", action="store_true")
    ap.add_argument("--news", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of markdown")
    args = ap.parse_args()

    ticker = yf.Ticker(args.ticker)
    data: dict[str, Any] = {}

    want_all = args.all
    wants_specific = any([args.options, args.list_expiries, args.earnings, args.divs, args.news])

    if want_all or not wants_specific:
        data["price"] = get_price_snapshot(ticker)

    if args.list_expiries:
        data["expiries"] = list_expiries(ticker)

    if args.options:
        data["options"] = get_option_chain(ticker, args.options, args.strike, args.right)

    if args.earnings or want_all:
        data["earnings"] = get_earnings(ticker)

    if args.divs or want_all:
        data["dividends"] = get_dividends(ticker)

    if args.news or want_all:
        data["news"] = get_news(ticker)

    if args.json:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(render_markdown(args.ticker.upper(), data))

    return 0


if __name__ == "__main__":
    sys.exit(main())
