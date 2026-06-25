"""
trader-agent research helper.

Deterministic data-gathering for the @trader agent's research checklist.
Replaces fragile LLM-driven math with explicit Python calculations.

Usage:
    python research.py <TICKER>
    python research.py <TICKER> --json
    python research.py <TICKER> --raw-dir <path>

Outputs:
    Markdown research note (default) or structured JSON (--json).

Requires: yfinance, pandas, lxml.
SEC EDGAR access is optional — script gracefully degrades when blocked.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
from typing import Any

import yfinance as yf
import pandas as pd

EARNINGS_LOOKBACK_QUARTERS = 8
RS_WINDOWS_DAYS = (21, 63)  # ~1m, ~3m of trading days
SECTOR_BENCHMARKS = {"SMH": "Semis ETF", "QQQ": "Nasdaq-100", "SPY": "S&P 500"}
OPTIONS_TARGET_DTE = 30  # we want IV at this horizon
OPTIONS_DTE_BAND = (21, 45)  # acceptable range for interpolation
LIQUIDITY_MAX_SPREAD_PCT = 1.0
LIQUIDITY_MIN_OI = 500


def _safe(value: Any) -> Any:
    """Coerce numpy/pandas scalars to plain Python types."""
    if value is None:
        return None
    try:
        if hasattr(value, "item"):
            return value.item()
    except Exception:
        pass
    return value


def _is_third_friday(date_obj: dt.date) -> bool:
    """3rd-Friday monthly expiry (deepest-liquidity class).

    Limitation: does NOT detect holiday-shifted monthlies (e.g. Thursday before Good Friday).
    Reflected in the field name `primary_is_third_friday` (not generic "is_standard_monthly").
    """
    return date_obj.weekday() == 4 and 15 <= date_obj.day <= 21


def _spread_pct_row(row) -> float | None:
    bid = float(row["bid"]) if pd.notna(row.get("bid")) else math.nan
    ask = float(row["ask"]) if pd.notna(row.get("ask")) else math.nan
    if math.isnan(bid) or math.isnan(ask):
        return None
    if bid < 0 or ask < 0 or ask < bid:
        return None  # crossed/invalid market
    mid = (bid + ask) / 2
    if mid <= 0:
        return None
    return round((ask - bid) / mid * 100, 2)


def _classify_liquidity(spread_pct: float | None, oi: int) -> str:
    """Tiered classification (PASS / MARGINAL / FAIL).

    PASS: spread ≤ 1% AND OI ≥ 500 — trade-ready.
    MARGINAL: spread 1–3% AND OI ≥ 500 — work limit orders, smaller size, user override required.
    FAIL: anything worse — do not trade.
    """
    if spread_pct is None:
        return "FAIL"
    if spread_pct <= LIQUIDITY_MAX_SPREAD_PCT and oi >= LIQUIDITY_MIN_OI:
        return "PASS"
    if spread_pct <= 3.0 and oi >= LIQUIDITY_MIN_OI:
        return "MARGINAL"
    return "FAIL"


def _liquid_strike_zone(df, last: float, side: str) -> dict:
    """For a chain side, return strikes that pass the liquidity gate (PASS-tier only)."""
    required = {"strike", "openInterest", "bid", "ask"}
    if df.empty or not required.issubset(df.columns):
        return {"strikes": [], "low": None, "high": None, "count": 0, "error": "missing strike/oi/bid/ask columns"}
    d = df.dropna(subset=list(required)).copy()
    if d.empty:
        return {"strikes": [], "low": None, "high": None, "count": 0}
    d["spread_pct"] = d.apply(_spread_pct_row, axis=1)
    # Dedupe to first occurrence per strike (handles non-standard adjusted contracts)
    d = d.drop_duplicates(subset=["strike"], keep="first")
    liquid = d[
        (d["openInterest"] >= LIQUIDITY_MIN_OI)
        & (d["spread_pct"].notna())
        & (d["spread_pct"] <= LIQUIDITY_MAX_SPREAD_PCT)
    ].sort_values("strike")
    if liquid.empty:
        return {"strikes": [], "low": None, "high": None, "count": 0}
    strikes = [
        {"strike": float(r["strike"]), "oi": int(r["openInterest"]), "spread_pct": float(r["spread_pct"])}
        for _, r in liquid.iterrows()
    ]
    # Detect non-contiguous gaps — count strikes between low and high that EXIST in the chain but failed
    all_strikes_in_range = sorted(d[(d["strike"] >= strikes[0]["strike"]) & (d["strike"] <= strikes[-1]["strike"])]["strike"].unique())
    has_gaps = len(all_strikes_in_range) > len(strikes)
    return {
        "strikes": strikes,
        "low": strikes[0]["strike"],
        "high": strikes[-1]["strike"],
        "count": len(strikes),
        "low_pct_from_spot": round((strikes[0]["strike"] / last - 1) * 100, 2),
        "high_pct_from_spot": round((strikes[-1]["strike"] / last - 1) * 100, 2),
        "has_gaps": has_gaps,
    }


def get_snapshot(t: yf.Ticker, hist) -> dict:
    info = t.info or {}
    closes = hist["Close"].tolist()
    last = float(closes[-1])
    highs_52w = hist["High"].tail(252).max()
    lows_52w = hist["Low"].tail(252).min()
    return {
        "last_close": round(last, 2),
        "data_through": hist.index[-1].strftime("%Y-%m-%d"),
        "market_cap": _safe(info.get("marketCap")),
        "shares_outstanding": _safe(info.get("sharesOutstanding")),
        "float_shares": _safe(info.get("floatShares")),
        "short_shares": _safe(info.get("sharesShort")),
        "short_ratio_days": _safe(info.get("shortRatio")),
        "avg_volume_30d": int(hist["Volume"].tail(30).mean()),
        "high_52w": round(float(highs_52w), 2),
        "low_52w": round(float(lows_52w), 2),
        "pct_off_high": round((last / float(highs_52w) - 1) * 100, 2),
        "pct_off_low": round((last / float(lows_52w) - 1) * 100, 2),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "beta": _safe(info.get("beta")),
        "forward_pe": _safe(info.get("forwardPE")),
        "trailing_pe": _safe(info.get("trailingPE")),
    }


def get_technicals(hist) -> dict:
    closes = hist["Close"].to_numpy()
    highs = hist["High"].to_numpy()
    lows = hist["Low"].to_numpy()
    vols = hist["Volume"].to_numpy()
    n = len(closes)
    last = float(closes[-1])

    def sma(window: int) -> float | None:
        if n < window:
            return None
        return round(float(closes[-window:].mean()), 2)

    sma20, sma50, sma200 = sma(20), sma(50), sma(200)
    trs = []
    for i in range(1, n):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr14 = float(sum(trs[-14:]) / 14) if len(trs) >= 14 else None

    rets = [math.log(closes[i] / closes[i - 1]) for i in range(n - 30, n)] if n >= 31 else []
    if rets:
        mu = sum(rets) / len(rets)
        var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
        rv30 = math.sqrt(var) * math.sqrt(252) * 100
    else:
        rv30 = None

    dist_days = 0
    for i in range(max(1, n - 25), n):
        if closes[i] < closes[i - 1] * 0.998 and vols[i] > vols[i - 1]:
            dist_days += 1

    trend = "mixed"
    if sma20 and sma50 and sma200:
        if sma20 > sma50 > sma200:
            trend = "20>50>200 (uptrend)"
        elif sma20 < sma50 < sma200:
            trend = "20<50<200 (downtrend)"

    return {
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "trend": trend,
        "atr14": round(atr14, 2) if atr14 else None,
        "atr14_pct_of_price": round(atr14 / last * 100, 2) if atr14 else None,
        "realized_vol_30d_pct": round(rv30, 1) if rv30 else None,
        "distribution_days_25d": dist_days,
    }


def get_options_snapshot(t: yf.Ticker, last: float) -> dict:
    """30-day IV by variance-time interpolation across nearby expiries, plus liquidity check
    and expected move from ATM straddle (sqrt-time scaled to 30 days)."""
    try:
        expiries = list(t.options or [])
    except Exception as e:
        return {"error": f"options unavailable: {e}"}
    if not expiries:
        return {"error": "no options listed"}

    today = dt.date.today()
    candidates = []
    for exp in expiries:
        try:
            edate = dt.datetime.strptime(exp, "%Y-%m-%d").date()
        except ValueError:
            continue
        dte = (edate - today).days
        if dte <= 0:
            continue
        candidates.append((dte, exp))
    candidates.sort()

    if not candidates:
        return {"error": "no future expiries"}

    def _coerce(df):
        df = df.copy()
        for col in ("strike", "bid", "ask", "lastPrice", "impliedVolatility", "openInterest", "volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    chains = {}
    # Keep loading until we either span the target or have 4 chains
    for dte, exp in candidates:
        if len(chains) >= 4 and chains and min(chains) <= OPTIONS_TARGET_DTE <= max(chains):
            break
        try:
            ch = t.option_chain(exp)
            calls = _coerce(ch.calls).dropna(subset=["strike", "impliedVolatility"])
            puts = _coerce(ch.puts).dropna(subset=["strike", "impliedVolatility"])
            if calls.empty or puts.empty:
                continue
            atm_call = calls.iloc[(calls["strike"] - last).abs().argmin()]
            atm_put = puts.iloc[(puts["strike"] - last).abs().argmin()]
            chains[dte] = {"expiry": exp, "atm_call": atm_call, "atm_put": atm_put, "calls": calls, "puts": puts}
        except Exception:
            continue

    if not chains:
        return {"error": "could not load any candidate chain"}

    dtes = sorted(chains.keys())
    atm_ivs = {d: float((chains[d]["atm_call"]["impliedVolatility"] + chains[d]["atm_put"]["impliedVolatility"]) / 2) for d in dtes}
    target = OPTIONS_TARGET_DTE
    if target <= dtes[0]:
        iv30 = atm_ivs[dtes[0]]
        method = f"earliest available (DTE={dtes[0]})"
    elif target >= dtes[-1]:
        iv30 = atm_ivs[dtes[-1]]
        method = f"latest available (DTE={dtes[-1]})"
    else:
        lo = max(d for d in dtes if d <= target)
        hi = min(d for d in dtes if d >= target)
        if lo == hi:
            iv30 = atm_ivs[lo]
            method = f"exact (DTE={lo})"
        else:
            # Interpolate in total-variance space: iv^2 * t
            var_lo = (atm_ivs[lo] ** 2) * lo
            var_hi = (atm_ivs[hi] ** 2) * hi
            w = (target - lo) / (hi - lo)
            var_target = var_lo * (1 - w) + var_hi * w
            iv30 = math.sqrt(var_target / target) if var_target > 0 else float("nan")
            method = f"variance-interp DTE {lo}->{hi}"

    primary_dte = min(dtes, key=lambda d: abs(d - target))
    primary = chains[primary_dte]
    atm_call = primary["atm_call"]
    atm_put = primary["atm_put"]

    # Mid-price preferred; fall back to lastPrice
    def _mid_or_last(row):
        bid = float(row["bid"]) if pd.notna(row.get("bid")) else math.nan
        ask = float(row["ask"]) if pd.notna(row.get("ask")) else math.nan
        last_px = float(row["lastPrice"]) if pd.notna(row.get("lastPrice")) else math.nan
        if not math.isnan(bid) and not math.isnan(ask) and bid > 0 and ask >= bid:
            return (bid + ask) / 2, "mid"
        return last_px, "last"

    call_px, call_src = _mid_or_last(atm_call)
    put_px, put_src = _mid_or_last(atm_put)
    em_pricing = f"call:{call_src}+put:{put_src}"
    if math.isnan(call_px) or math.isnan(put_px):
        straddle = None
        expected_move_primary_pct = None
        expected_move_30d_pct = None
    else:
        straddle = call_px + put_px
        expected_move_primary_pct = round(straddle / last * 100, 2)
        # sqrt-time scale to 30 days
        expected_move_30d_pct = round(expected_move_primary_pct * math.sqrt(30 / primary_dte), 2) if primary_dte > 0 else None

    # Liquidity check
    def spread_pct(row):
        bid = float(row["bid"]) if pd.notna(row.get("bid")) else math.nan
        ask = float(row["ask"]) if pd.notna(row.get("ask")) else math.nan
        if math.isnan(bid) or math.isnan(ask):
            return None
        mid = (bid + ask) / 2
        return round((ask - bid) / mid * 100, 2) if mid > 0 else None

    atm_call_spread = spread_pct(atm_call)
    atm_put_spread = spread_pct(atm_put)
    atm_call_oi = int(atm_call["openInterest"]) if pd.notna(atm_call.get("openInterest")) else 0
    liquidity_ok = (
        atm_call_spread is not None
        and atm_call_spread <= LIQUIDITY_MAX_SPREAD_PCT
        and atm_call_oi >= LIQUIDITY_MIN_OI
    )

    def _top_oi(df, n=3):
        d = df.dropna(subset=["openInterest"])
        if d.empty:
            return []
        return d.nlargest(n, "openInterest")[["strike", "openInterest", "volume", "impliedVolatility"]].to_dict("records")

    top_call_oi = _top_oi(primary["calls"])
    top_put_oi = _top_oi(primary["puts"])

    def find_by_delta(df, target_delta):
        if "delta" not in df.columns:
            return None
        df2 = df.dropna(subset=["delta"]).copy()
        if df2.empty:
            return None
        df2["dist"] = (df2["delta"].abs() - target_delta).abs()
        return df2.sort_values("dist").iloc[0]

    skew_25d = None
    p25 = find_by_delta(primary["puts"], 0.25)
    c25 = find_by_delta(primary["calls"], 0.25)
    if p25 is not None and c25 is not None:
        skew_25d = round(float(p25["impliedVolatility"]) - float(c25["impliedVolatility"]), 4)

    primary_date = dt.datetime.strptime(primary["expiry"], "%Y-%m-%d").date()
    is_third_friday = _is_third_friday(primary_date)
    call_zone = _liquid_strike_zone(primary["calls"], last, "call")
    put_zone = _liquid_strike_zone(primary["puts"], last, "put")

    return {
        "primary_expiry": primary["expiry"],
        "primary_dte": primary_dte,
        "primary_is_third_friday": is_third_friday,
        "iv30_atm": round(iv30 * 100, 1) if iv30 == iv30 else None,  # NaN check
        "iv30_method": method,
        "expected_move_primary_pct": expected_move_primary_pct,
        "expected_move_primary_usd": round(straddle, 2) if straddle is not None else None,
        "expected_move_30d_pct": expected_move_30d_pct,
        "expected_move_pricing": em_pricing,
        "atm_call_strike": float(atm_call["strike"]),
        "atm_call_bid_ask_spread_pct": atm_call_spread,
        "atm_call_oi": atm_call_oi,
        "atm_put_bid_ask_spread_pct": atm_put_spread,
        "liquidity_ok": liquidity_ok,
        "tradeable_call_zone": call_zone,
        "tradeable_put_zone": put_zone,
        "skew_25d_proxy": skew_25d,
        "top_call_oi": top_call_oi,
        "top_put_oi": top_put_oi,
        "n_expiries": len(expiries),
        "all_expiries": list(expiries),
    }


def check_spread(ticker: str, expiry: str, long_strike: float, short_strike: float, right: str) -> dict:
    """Per-leg liquidity check for a vertical spread the agent is considering.

    `right` is 'call' or 'put'. Returns spread/OI for each leg + a verdict (PASS/MARGINAL/FAIL).
    """
    right = right.lower()
    if right not in ("call", "put"):
        return {"error": "right must be 'call' or 'put'"}
    try:
        expiry_date = dt.datetime.strptime(expiry, "%Y-%m-%d").date()
    except ValueError:
        return {"error": f"expiry {expiry} not in YYYY-MM-DD format"}
    dte = (expiry_date - dt.date.today()).days
    if dte <= 0:
        return {"error": f"expiry {expiry} is not future-dated (DTE={dte})"}

    t = yf.Ticker(ticker)
    available = t.options or []
    if expiry not in available:
        return {"error": f"expiry {expiry} not in chain; available: {list(available)[:6]}..."}
    try:
        ch = t.option_chain(expiry)
    except Exception as e:
        return {"error": f"chain load failed: {e}"}

    df = ch.calls if right == "call" else ch.puts
    required = {"strike", "bid", "ask", "openInterest"}
    if not required.issubset(df.columns):
        return {"error": f"chain missing required columns: {required - set(df.columns)}"}
    for col in ("strike", "bid", "ask", "lastPrice", "impliedVolatility", "openInterest", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["strike"])

    def leg(strike: float) -> dict:
        sub = df[(df["strike"] - strike).abs() < 0.001]
        if sub.empty:
            return {"strike": strike, "error": "strike not listed", "tier": "FAIL", "passes_gate": False}
        if len(sub) > 1:
            # Non-standard adjusted contracts can duplicate a strike. Use the highest-OI row.
            sub = sub.sort_values("openInterest", ascending=False, na_position="last")
        row = sub.iloc[0]
        sp = _spread_pct_row(row)
        oi = int(row["openInterest"]) if pd.notna(row.get("openInterest")) else 0
        bid = float(row["bid"]) if pd.notna(row.get("bid")) else None
        ask = float(row["ask"]) if pd.notna(row.get("ask")) else None
        mid = round((bid + ask) / 2, 2) if (bid is not None and ask is not None and ask >= bid) else None
        tier = _classify_liquidity(sp, oi)
        return {
            "strike": float(strike),
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread_pct_of_mid": sp,
            "open_interest": oi,
            "tier": tier,
            "passes_gate": tier == "PASS",
            "duplicate_contracts": len(sub) > 1,
        }

    long_leg = leg(long_strike)
    short_leg = leg(short_strike)
    spread_width = abs(short_strike - long_strike)

    # Estimate net at mid-of-mids
    if long_leg.get("mid") is not None and short_leg.get("mid") is not None:
        net = round(long_leg["mid"] - short_leg["mid"], 2)
        net_label = "debit" if net > 0 else "credit"
    else:
        net = None
        net_label = None

    # Classify structure
    structure = None
    if right == "call":
        if long_strike < short_strike:
            structure = "bull_call_debit"
        elif long_strike > short_strike:
            structure = "bear_call_credit"
    else:  # put
        if long_strike > short_strike:
            structure = "bear_put_debit"
        elif long_strike < short_strike:
            structure = "bull_put_credit"

    # Validate spread economics
    economics_warning = None
    if net is not None and spread_width > 0:
        if net_label == "debit" and not (0 < abs(net) < spread_width):
            economics_warning = f"debit ${abs(net)} not in valid range (0, {spread_width}) — bad quotes"
        if net_label == "credit" and not (0 < abs(net) < spread_width):
            economics_warning = f"credit ${abs(net)} not in valid range (0, {spread_width}) — bad quotes"

    # Verdict
    long_tier = long_leg.get("tier", "FAIL")
    short_tier = short_leg.get("tier", "FAIL")
    worst = "FAIL" if "FAIL" in (long_tier, short_tier) else ("MARGINAL" if "MARGINAL" in (long_tier, short_tier) else "PASS")
    if economics_warning:
        worst = "FAIL"
    verdict_text = {
        "PASS": "TRADEABLE",
        "MARGINAL": "MARGINAL — work limit orders, accept slippage, smaller size; user override required",
        "FAIL": "FAIL — one or both legs miss the liquidity gate (or bad quote economics)",
    }[worst]

    return {
        "ticker": ticker.upper(),
        "expiry": expiry,
        "dte": dte,
        "is_third_friday": _is_third_friday(expiry_date),
        "right": right,
        "structure": structure,
        "long_leg": long_leg,
        "short_leg": short_leg,
        "spread_width": spread_width,
        "estimated_net_at_mid": net,
        "net_label": net_label,
        "economics_warning": economics_warning,
        "tier": worst,
        "verdict": verdict_text,
        "thresholds": {
            "pass": {"spread_pct": LIQUIDITY_MAX_SPREAD_PCT, "oi": LIQUIDITY_MIN_OI},
            "marginal": {"spread_pct": 3.0, "oi": LIQUIDITY_MIN_OI},
        },
    }


def get_earnings_move_history(t: yf.Ticker, hist_long, quarters: int = EARNINGS_LOOKBACK_QUARTERS) -> dict:
    """Compute earnings-reaction % move using prior-close -> next-close.

    Note: We do NOT attempt to detect BMO vs AMC reliably (Yahoo's hour field is unreliable).
    Prior-close -> next-close is a safe consistent window that captures the reaction in either case.
    `hist_long` should be ~3 years of daily prices so we can cover the requested lookback.
    """
    try:
        ed = t.get_earnings_dates(limit=quarters * 3)
    except Exception as e:
        return {"error": f"earnings dates unavailable: {e}"}
    if ed is None or ed.empty:
        return {"error": "no earnings history"}

    moves = []
    closes = hist_long["Close"]
    # Make tz-naive date comparisons safe
    close_dates = closes.index.tz_localize(None).date if closes.index.tz is not None else closes.index.date

    for ts, row in ed.iterrows():
        reported = row.get("Reported EPS") if "Reported EPS" in row else None
        if reported is None or (isinstance(reported, float) and math.isnan(reported)):
            continue
        try:
            edate = ts.date() if hasattr(ts, "date") else ts
        except Exception:
            continue
        try:
            before_mask = close_dates < edate  # strictly before earnings day
            after_mask = close_dates >= edate  # earnings day onwards (covers AMC where reaction is next day, and BMO where reaction is same day)
            before_idx = closes.index[before_mask]
            after_idx = closes.index[after_mask]
            if len(before_idx) == 0 or len(after_idx) < 2:
                continue
            pre = float(closes.loc[before_idx[-1]])
            # post = first trading close on or after earnings day + one trading day (covers AMC case)
            post = float(closes.loc[after_idx[1]])
            move_pct = (post / pre - 1) * 100
            moves.append({
                "earnings_date": edate.isoformat(),
                "pre_close": round(pre, 2),
                "post_close": round(post, 2),
                "move_pct": round(move_pct, 2),
                "window": "prior_close_to_close+1",
            })
        except Exception:
            continue
        if len(moves) >= quarters:
            break

    if not moves:
        return {"error": "could not compute any moves (likely insufficient price history)"}

    abs_moves = [abs(m["move_pct"]) for m in moves]
    return {
        "moves": moves,
        "avg_abs_move_pct": round(sum(abs_moves) / len(abs_moves), 2),
        "max_abs_move_pct": round(max(abs_moves), 2),
        "up_count": sum(1 for m in moves if m["move_pct"] > 0),
        "down_count": sum(1 for m in moves if m["move_pct"] < 0),
        "n_quarters": len(moves),
        "method": "prior trading close -> close one trading day after earnings date (captures both BMO and AMC)",
    }


def get_relative_strength(ticker: str, target_hist) -> dict:
    """% return of ticker vs benchmarks over 21d and 63d, plus RS diff."""
    ticker_u = ticker.upper()
    bench_tickers = [b for b in SECTOR_BENCHMARKS.keys() if b != ticker_u]
    download_set = bench_tickers + [ticker_u]
    if len(download_set) < 2:
        return {"error": "ticker is a benchmark; no peers to compare against"}
    try:
        data = yf.download(download_set, period="6mo", interval="1d", progress=False, auto_adjust=True)["Close"]
    except Exception as e:
        return {"error": f"benchmark download failed: {e}"}
    if data is None or data.empty:
        return {"error": "no benchmark data"}
    if ticker_u not in data.columns:
        return {"error": f"yfinance did not return data for {ticker_u}"}

    result = {}
    for window in RS_WINDOWS_DAYS:
        label = f"{window}d"
        target_series = data[ticker_u].dropna()
        if len(target_series) <= window:
            result[label] = {"error": f"insufficient history ({len(target_series)} rows, need >{window})"}
            continue
        tret = float(target_series.iloc[-1] / target_series.iloc[-window - 1] - 1) * 100
        row = {"ticker_return_pct": round(tret, 2), "benchmarks": {}}
        for b in bench_tickers:
            if b not in data.columns:
                continue
            bseries = data[b].dropna()
            if len(bseries) <= window:
                continue
            bret = float(bseries.iloc[-1] / bseries.iloc[-window - 1] - 1) * 100
            row["benchmarks"][b] = {
                "label": SECTOR_BENCHMARKS[b],
                "return_pct": round(bret, 2),
                "rs_diff_pct": round(tret - bret, 2),
            }
        result[label] = row
    return result


def get_fundamentals(t: yf.Ticker) -> dict:
    """Quarterly revenue, EPS, and SEC-derived financials via yfinance (works when SEC blocked)."""
    out: dict = {"source": "yfinance (SEC-derived, no direct SEC.gov access required)"}
    try:
        qf = t.quarterly_financials
        if qf is not None and not qf.empty:
            rev = []
            for col in qf.columns[:4]:
                rev.append({
                    "period_end": col.strftime("%Y-%m-%d"),
                    "revenue": _safe(qf.loc["Total Revenue", col]) if "Total Revenue" in qf.index else None,
                    "net_income": _safe(qf.loc["Net Income", col]) if "Net Income" in qf.index else None,
                })
            out["quarterly_financials"] = rev
        else:
            out["quarterly_financials_error"] = "unavailable from yfinance"
    except Exception as e:
        out["quarterly_financials_error"] = str(e)

    try:
        cf = t.cashflow
        if cf is not None and not cf.empty:
            col = cf.columns[0]
            fcf = None
            for key in ("Free Cash Flow", "Operating Cash Flow"):
                if key in cf.index:
                    fcf = _safe(cf.loc[key, col])
                    break
            out["fiscal_year_fcf"] = {"period": col.strftime("%Y-%m-%d"), "value": fcf}
        else:
            out["cashflow_error"] = "unavailable from yfinance"
    except Exception as e:
        out["cashflow_error"] = str(e)

    try:
        ins = t.insider_transactions
        if ins is not None and not ins.empty and "Value" in ins.columns:
            cutoff = dt.datetime.now() - dt.timedelta(days=90)
            recent = ins[ins["Start Date"] >= cutoff] if "Start Date" in ins.columns else ins.head(20)
            if not recent.empty:
                out["insider_90d"] = {
                    "net_value_usd": float(recent["Value"].sum()),
                    "transaction_count": int(len(recent)),
                    "caveat": "yfinance insider feed is partial vs full SEC Form 4 history; treat as directional only",
                }
            else:
                out["insider_90d_error"] = "no insider transactions in last 90d"
        else:
            out["insider_90d_error"] = "unavailable from yfinance"
    except Exception as e:
        out["insider_90d_error"] = str(e)

    return out


def gather(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    hist = t.history(period="1y", interval="1d", auto_adjust=True)
    if hist is None or hist.empty:
        raise SystemExit(f"No price history available for {ticker}")
    # Separate longer history specifically for earnings move lookback (needs ~2y to cover 8 quarters)
    try:
        hist_long = t.history(period="3y", interval="1d", auto_adjust=True)
        if hist_long is None or hist_long.empty:
            hist_long = hist
    except Exception:
        hist_long = hist
    last = float(hist["Close"].iloc[-1])

    return {
        "ticker": ticker.upper(),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "snapshot": get_snapshot(t, hist),
        "technicals": get_technicals(hist),
        "options": get_options_snapshot(t, last),
        "earnings_history": get_earnings_move_history(t, hist_long),
        "relative_strength": get_relative_strength(ticker, hist),
        "fundamentals": get_fundamentals(t),
    }


def render_markdown(data: dict) -> str:
    s = data["snapshot"]
    tch = data["technicals"]
    opt = data["options"]
    er = data["earnings_history"]
    rs = data["relative_strength"]
    fnd = data["fundamentals"]

    lines = []
    lines.append(f"# Research: {data['ticker']} — {dt.date.today().isoformat()}")
    lines.append("")
    lines.append(f"> Generated by `scripts/research.py` at {data['generated_at']}.")
    lines.append("")

    lines.append("## Snapshot")
    lines.append(f"- Last close: **${s['last_close']}** (data through {s['data_through']})")
    lines.append(f"- Market cap: {s['market_cap']:,}" if s.get('market_cap') else "- Market cap: n/a")
    lines.append(f"- Sector / Industry: {s.get('sector')} / {s.get('industry')}")
    lines.append(f"- Float: {s['float_shares']:,}" if s.get('float_shares') else "")
    lines.append(f"- Short shares: {s['short_shares']:,} ({s.get('short_ratio_days')} days to cover)" if s.get('short_shares') else "")
    lines.append(f"- Avg vol 30d: {s['avg_volume_30d']:,}")
    lines.append(f"- 52w high / low: ${s['high_52w']} / ${s['low_52w']}  ({s['pct_off_high']}% / +{s['pct_off_low']}%)")
    lines.append(f"- Beta: {s.get('beta')}  Forward P/E: {s.get('forward_pe')}  Trailing P/E: {s.get('trailing_pe')}")

    lines.append("")
    lines.append("## Technicals")
    lines.append(f"- SMA 20/50/200: ${tch['sma20']} / ${tch['sma50']} / ${tch['sma200']}")
    lines.append(f"- Trend: **{tch['trend']}**")
    lines.append(f"- ATR(14): ${tch['atr14']} ({tch['atr14_pct_of_price']}% of price)")
    lines.append(f"- 30d realized vol: {tch['realized_vol_30d_pct']}% annualized")
    lines.append(f"- Distribution days last 25: {tch['distribution_days_25d']}")

    lines.append("")
    lines.append("## Options")
    if "error" in opt:
        lines.append(f"- ERROR: {opt['error']}")
    else:
        lines.append(f"- Primary chain: {opt['primary_expiry']} ({opt['primary_dte']} DTE) — "
                     f"{'**3rd-Friday monthly**' if opt.get('primary_is_third_friday') else '⚠️ NOT a 3rd-Friday monthly (weekly/quarterly — typically thinner)'}")
        lines.append(f"- **30d ATM IV: {opt['iv30_atm']}%** ({opt['iv30_method']})" if opt.get("iv30_atm") is not None else "- 30d ATM IV: unavailable")
        em_primary = opt.get("expected_move_primary_pct")
        em_30 = opt.get("expected_move_30d_pct")
        if em_primary is not None:
            lines.append(
                f"- Expected move to primary expiry ({opt['primary_dte']} DTE) from ATM straddle: "
                f"**±{em_primary}%** = ±${opt.get('expected_move_primary_usd')}  _(pricing: {opt.get('expected_move_pricing')})_"
            )
            if em_30 is not None:
                lines.append(f"- Scaled to 30d (sqrt-time): **±{em_30}%**")
        else:
            lines.append("- Expected move: unavailable (no valid bid/ask or last price on ATM straddle)")
        lines.append(f"- 25-delta skew (put IV − call IV): {opt['skew_25d_proxy']}" if opt.get("skew_25d_proxy") is not None else "- 25-delta skew: not surfaced (delta not in chain)")
        lines.append(f"- Liquidity check on ATM call (strike ${opt['atm_call_strike']}): "
                     f"spread {opt['atm_call_bid_ask_spread_pct']}% of mid, OI {opt['atm_call_oi']:,} "
                     f"→ **{'PASS' if opt['liquidity_ok'] else 'FAIL'}** "
                     f"(threshold: spread ≤{LIQUIDITY_MAX_SPREAD_PCT}%, OI ≥{LIQUIDITY_MIN_OI})")
        # Tradeable strike zone
        cz = opt.get("tradeable_call_zone") or {}
        pz = opt.get("tradeable_put_zone") or {}
        lines.append("")
        lines.append("### Tradeable strike zone (primary expiry; OI ≥{} AND spread ≤{}%)".format(LIQUIDITY_MIN_OI, LIQUIDITY_MAX_SPREAD_PCT))
        if cz.get("count"):
            gap_note = " (⚠️ gaps — not a continuous range)" if cz.get("has_gaps") else ""
            lines.append(f"- **Calls:** ${cz['low']:.2f} → ${cz['high']:.2f}  ({cz['count']} strikes; "
                         f"{cz['low_pct_from_spot']:+.1f}% to {cz['high_pct_from_spot']:+.1f}% from spot){gap_note}")
        else:
            lines.append("- **Calls:** NO strikes pass the liquidity gate on this expiry. Try a 3rd-Friday monthly or skip options.")
        if pz.get("count"):
            gap_note = " (⚠️ gaps — not a continuous range)" if pz.get("has_gaps") else ""
            lines.append(f"- **Puts:**  ${pz['low']:.2f} → ${pz['high']:.2f}  ({pz['count']} strikes; "
                         f"{pz['low_pct_from_spot']:+.1f}% to {pz['high_pct_from_spot']:+.1f}% from spot){gap_note}")
        else:
            lines.append("- **Puts:** NO strikes pass the liquidity gate on this expiry.")
        lines.append(f"- _Use `python scripts/research.py check-spread {data['ticker']} {opt['primary_expiry']} <long> <short> call|put` to verify a specific spread before sizing._")
        lines.append(f"- Total expiries listed: {opt['n_expiries']}")

    lines.append("")
    lines.append("## Earnings move history")
    if "error" in er:
        lines.append(f"- ERROR: {er['error']}")
    else:
        lines.append(f"- Last {er['n_quarters']} quarters — avg ABS move: **±{er['avg_abs_move_pct']}%**, max: ±{er['max_abs_move_pct']}%")
        lines.append(f"- Up: {er['up_count']} / Down: {er['down_count']}")
        lines.append("| Earnings date | Pre | Post | Move |")
        lines.append("|---|---|---|---|")
        for m in er["moves"]:
            lines.append(f"| {m['earnings_date']} | ${m['pre_close']} | ${m['post_close']} | {m['move_pct']:+.2f}% |")

    lines.append("")
    lines.append("## Relative strength")
    if "error" in rs:
        lines.append(f"- ERROR: {rs['error']}")
    else:
        for window, row in rs.items():
            lines.append(f"### {window}")
            if "error" in row:
                lines.append(f"- ERROR: {row['error']}")
                continue
            lines.append(f"- {data['ticker']} return: {row['ticker_return_pct']}%")
            for b, info in row["benchmarks"].items():
                arrow = "outperforming" if info["rs_diff_pct"] > 0 else "underperforming"
                lines.append(f"  - vs {b} ({info['label']}): {info['return_pct']}% → **{arrow} by {abs(info['rs_diff_pct'])} pts**")

    lines.append("")
    lines.append("## Fundamentals")
    lines.append(f"- Source: {fnd.get('source')}")
    if "quarterly_financials" in fnd:
        lines.append("- Last 4Q revenue:")
        for q in fnd["quarterly_financials"]:
            rev = f"${q['revenue']:,.0f}" if q.get("revenue") else "n/a"
            lines.append(f"  - {q['period_end']}: {rev}")
    if "fiscal_year_fcf" in fnd:
        f = fnd["fiscal_year_fcf"]
        lines.append(f"- Most recent FY FCF ({f['period']}): ${f['value']:,.0f}" if f.get('value') else f"- FCF for {f['period']}: n/a")
    if "insider_90d" in fnd:
        ins = fnd["insider_90d"]
        lines.append(f"- Insider net value (90d, yfinance): ${ins['net_value_usd']:,.0f} across {ins['transaction_count']} transactions")
        lines.append(f"  - _{ins['caveat']}_")

    lines.append("")
    lines.append("## Data gaps & caveats")
    lines.append("- Macro (SPY/VIX/10Y/DXY) not gathered by this script — agent should fetch via FRED MCP or web_search.")
    lines.append("- Recent news headlines not included — agent should fetch via yahoo-finance MCP `get_news`.")
    lines.append("- 10-Q risk factors not included — agent should fetch via SEC EDGAR MCP, fall back to web_search if SEC unreachable.")
    lines.append("- IV rank/percentile (1-year context) not computed — yfinance does not expose historical IV. Use the 30d realized vol as a rough comparison; or use a paid feed.")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Trader-agent research helper")
    sub = ap.add_subparsers(dest="cmd")

    # Default subcommand: full research note (backwards compatible — also works without "research")
    rp = sub.add_parser("research", help="Full research note for a ticker (default)")
    rp.add_argument("ticker")
    rp.add_argument("--json", action="store_true", help="Emit raw JSON instead of markdown")
    rp.add_argument("--raw-dir", help="Also write raw JSON to this directory")
    rp.add_argument("--out", help="Write rendered markdown to this file (default: stdout)")

    # New: per-leg liquidity check for a vertical spread
    cs = sub.add_parser("check-spread", help="Per-leg liquidity check for a vertical spread")
    cs.add_argument("ticker")
    cs.add_argument("expiry", help="YYYY-MM-DD")
    cs.add_argument("long_strike", type=float)
    cs.add_argument("short_strike", type=float)
    cs.add_argument("right", choices=["call", "put"])
    cs.add_argument("--json", action="store_true")

    # Backwards-compat: if first arg looks like a ticker (no known subcommand), inject "research"
    raw_argv = sys.argv[1:]
    known_cmds = {"research", "check-spread", "-h", "--help"}
    if raw_argv and raw_argv[0] not in known_cmds:
        raw_argv = ["research"] + raw_argv

    args = ap.parse_args(raw_argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if args.cmd == "check-spread":
        result = check_spread(args.ticker, args.expiry, args.long_strike, args.short_strike, args.right)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            _print_check_spread(result)
        return 0 if "error" not in result else 1

    # default: research
    data = gather(args.ticker)
    if args.raw_dir:
        os.makedirs(args.raw_dir, exist_ok=True)
        with open(os.path.join(args.raw_dir, f"{args.ticker.upper()}-research-raw.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    payload = json.dumps(data, indent=2, default=str) if args.json else render_markdown(data)
    if args.out:
        out_dir = os.path.dirname(args.out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"Wrote {args.out}")
    else:
        print(payload)
    return 0


def _print_check_spread(r: dict) -> None:
    if "error" in r:
        print(f"ERROR: {r['error']}")
        return
    expiry_kind = "3rd-Friday monthly" if r["is_third_friday"] else "NOT 3rd-Friday (weekly/quarterly)"
    print(f"# Spread check: {r['ticker']} {r['expiry']} ({r['dte']} DTE, {expiry_kind})")
    print(f"Structure: {r.get('structure')}")
    print(f"Long  {r['right']} ${r['long_leg']['strike']}:  bid={r['long_leg'].get('bid')} ask={r['long_leg'].get('ask')} "
          f"mid={r['long_leg'].get('mid')} spread={r['long_leg'].get('spread_pct_of_mid')}% OI={r['long_leg'].get('open_interest')}  "
          f"→ {r['long_leg'].get('tier')}")
    print(f"Short {r['right']} ${r['short_leg']['strike']}: bid={r['short_leg'].get('bid')} ask={r['short_leg'].get('ask')} "
          f"mid={r['short_leg'].get('mid')} spread={r['short_leg'].get('spread_pct_of_mid')}% OI={r['short_leg'].get('open_interest')}  "
          f"→ {r['short_leg'].get('tier')}")
    print(f"Width: ${r['spread_width']}  Estimated net at mid: ${r['estimated_net_at_mid']} ({r['net_label']})")
    if r.get("economics_warning"):
        print(f"⚠️  {r['economics_warning']}")
    print(f"Verdict: **{r['verdict']}**")
    print(f"Tiers — PASS: spread ≤{r['thresholds']['pass']['spread_pct']}% AND OI ≥{r['thresholds']['pass']['oi']}.  "
          f"MARGINAL: spread ≤{r['thresholds']['marginal']['spread_pct']}% AND OI ≥{r['thresholds']['marginal']['oi']}.  "
          f"Else FAIL.")


if __name__ == "__main__":
    sys.exit(main())
