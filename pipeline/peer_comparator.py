from __future__ import annotations
"""
peer_comparator.py — Classify companies by GICS sector + market cap tier,
build sector ETF proxy peer returns, and compute alpha vs. peers.

Peer group methodology:
  - Sector: determined via yfinance Ticker.info['sector'] (GICS-aligned)
  - Market cap tiers: Small (<$2B), Mid ($2B–$10B), Large (>$10B)
  - Peer index: corresponding SPDR Select Sector ETF return over the same
    calendar window as the incident (T-1 through T+30/60/90)
  - Alpha = company return - peer ETF return at each interval

Sector ETF map (SPDR Select Sector ETFs):
  Information Technology  → XLK
  Financials              → XLF
  Health Care             → XLV
  Energy                  → XLE
  Industrials             → XLI
  Consumer Discretionary  → XLY
  Consumer Staples        → XLP
  Utilities               → XLU
  Real Estate             → XLRE
  Communication Services  → XLC
  Materials               → XLB
  (default / unknown)     → SPY
"""

import time
from datetime import datetime, timedelta

import yfinance as yf

SECTOR_ETF_MAP = {
    "Information Technology": "XLK",
    "Technology": "XLK",
    "Financials": "XLF",
    "Financial Services": "XLF",
    "Health Care": "XLV",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Materials": "XLB",
}

CAP_TIERS = [
    ("small", 0, 2_000_000_000),
    ("mid", 2_000_000_000, 10_000_000_000),
    ("large", 10_000_000_000, float("inf")),
]

# Cache ETF price pulls to avoid redundant API calls
_etf_price_cache: dict[str, dict] = {}


def classify_cap_tier(market_cap: int | None) -> str:
    if market_cap is None:
        return "unknown"
    for tier, low, high in CAP_TIERS:
        if low <= market_cap < high:
            return tier
    return "large"


def get_company_info(ticker: str) -> dict:
    """
    Fetch sector and market cap for a ticker via yfinance.
    Returns {"sector": str, "cap_tier": str, "market_cap_usd": int, "peer_etf": str}
    """
    result = {
        "sector": "Unknown",
        "cap_tier": "unknown",
        "market_cap_usd": None,
        "peer_etf": "SPY",
    }
    try:
        info = yf.Ticker(ticker).info
        time.sleep(0.5)

        sector = info.get("sector") or info.get("sectorDisp") or "Unknown"
        market_cap = info.get("marketCap")

        result["sector"] = sector
        result["market_cap_usd"] = market_cap
        result["cap_tier"] = classify_cap_tier(market_cap)
        result["peer_etf"] = SECTOR_ETF_MAP.get(sector, "SPY")
    except Exception as e:
        print(f"    Warning: could not fetch info for {ticker}: {e}")

    return result


def _get_etf_return(etf: str, filing_date: str, days_offset: int) -> float | None:
    """
    Compute the return of an ETF from T-1 (day before filing_date) to T+days_offset.
    Uses a cache to avoid redundant yfinance calls.
    """
    cache_key = f"{etf}:{filing_date}"
    if cache_key not in _etf_price_cache:
        try:
            filing_dt = datetime.strptime(filing_date, "%Y-%m-%d")
            start = (filing_dt - timedelta(days=10)).strftime("%Y-%m-%d")
            end = (filing_dt + timedelta(days=105)).strftime("%Y-%m-%d")
            hist = yf.Ticker(etf).history(start=start, end=end, auto_adjust=True)
            time.sleep(0.5)
            _etf_price_cache[cache_key] = hist
        except Exception as e:
            print(f"    Warning: ETF price fetch failed for {etf}: {e}")
            _etf_price_cache[cache_key] = None

    hist = _etf_price_cache[cache_key]
    if hist is None or hist.empty:
        return None

    filing_dt = datetime.strptime(filing_date, "%Y-%m-%d")

    # T-1 baseline
    baseline = None
    for offset in range(6):
        check = (filing_dt - timedelta(days=1 + offset)).strftime("%Y-%m-%d")
        matches = hist[hist.index.strftime("%Y-%m-%d") == check]
        if not matches.empty:
            baseline = float(matches["Close"].iloc[0])
            break

    if not baseline or baseline == 0:
        return None

    # T+days_offset price
    target_dt = filing_dt + timedelta(days=days_offset)
    price = None
    for offset in range(6):
        check = (target_dt + timedelta(days=offset)).strftime("%Y-%m-%d")
        matches = hist[hist.index.strftime("%Y-%m-%d") == check]
        if not matches.empty:
            price = float(matches["Close"].iloc[0])
            break

    if price is None:
        return None

    return round((price - baseline) / baseline, 6)


def enrich_with_peers(incidents: list[dict]) -> list[dict]:
    """
    Add sector, cap_tier, peer_etf, peer returns, and alpha to each incident.
    """
    total = len(incidents)
    for i, incident in enumerate(incidents):
        ticker = incident.get("ticker")
        filing_date = incident.get("filing_date")

        if not ticker or not filing_date:
            continue

        print(f"  [{i+1}/{total}] Peer classify: {ticker}")

        # Company classification
        info = get_company_info(ticker)
        incident.update(info)

        etf = info["peer_etf"]

        # Peer ETF returns at each interval
        for key, days in [("t0", 0), ("t30", 30), ("t60", 60), ("t90", 90)]:
            peer_return = _get_etf_return(etf, filing_date, days)
            incident[f"peer_return_{key}"] = peer_return

            # Alpha = company return - peer return
            company_return = incident.get(f"return_{key}")
            if company_return is not None and peer_return is not None:
                incident[f"alpha_{key}"] = round(company_return - peer_return, 6)
            else:
                incident[f"alpha_{key}"] = None

    return incidents
