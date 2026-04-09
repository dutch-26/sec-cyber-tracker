"""
stock_tracker.py — Track stock price performance around SEC cybersecurity incident disclosures.

For each incident, fetches:
  - T-1: closing price the trading day before the 8-K filing date (baseline)
  - T+0: closing price on the filing date itself
  - T+30, T+60, T+90: closing prices at 30-day increments post-filing

All returns are expressed as percentage change from the T-1 baseline.
"""

import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


# Calendar offsets → approximate trading day counts
TRADING_DAY_OFFSETS = {
    "t0": 0,
    "t30": 21,   # ~21 trading days ≈ 30 calendar days
    "t60": 42,
    "t90": 63,
}


def _next_trading_day_price(history: pd.DataFrame, target_date: datetime) -> float | None:
    """
    Find the closing price on or after target_date within history.
    Returns None if no price is found within 5 trading days.
    """
    for offset in range(6):
        check = target_date + timedelta(days=offset)
        check_str = check.strftime("%Y-%m-%d")
        # history index may be DatetimeIndex — normalize
        matches = history[history.index.strftime("%Y-%m-%d") == check_str]
        if not matches.empty:
            return float(matches["Close"].iloc[0])
    return None


def _prev_trading_day_price(history: pd.DataFrame, target_date: datetime) -> float | None:
    """
    Find the closing price on or before target_date within history.
    Returns None if no price found within 5 trading days prior.
    """
    for offset in range(6):
        check = target_date - timedelta(days=offset)
        check_str = check.strftime("%Y-%m-%d")
        matches = history[history.index.strftime("%Y-%m-%d") == check_str]
        if not matches.empty:
            return float(matches["Close"].iloc[0])
    return None


def get_price_data(ticker: str, filing_date: str) -> dict:
    """
    Fetch price data for a ticker around a filing date.

    Returns a dict with:
      price_baseline, price_t0, price_t30, price_t60, price_t90
      return_t0, return_t30, return_t60, return_t90
      price_available (bool)
    """
    result = {
        "price_baseline": None,
        "price_t0": None,
        "price_t30": None,
        "price_t60": None,
        "price_t90": None,
        "return_t0": None,
        "return_t30": None,
        "return_t60": None,
        "return_t90": None,
        "price_available": False,
    }

    try:
        filing_dt = datetime.strptime(filing_date, "%Y-%m-%d")
    except ValueError:
        return result

    # Fetch a wide window: 10 days before filing through 100 calendar days after
    start = (filing_dt - timedelta(days=10)).strftime("%Y-%m-%d")
    end = (filing_dt + timedelta(days=105)).strftime("%Y-%m-%d")

    try:
        tkr = yf.Ticker(ticker)
        history = tkr.history(start=start, end=end, auto_adjust=True)
        time.sleep(0.5)  # Polite delay
    except Exception as e:
        print(f"    yfinance error for {ticker}: {e}")
        return result

    if history.empty:
        print(f"    No price data for {ticker}")
        return result

    # T-1 baseline
    baseline = _prev_trading_day_price(history, filing_dt - timedelta(days=1))
    if baseline is None:
        # Fallback: try day before filing
        baseline = _prev_trading_day_price(history, filing_dt)
    if baseline is None or baseline == 0:
        return result

    result["price_baseline"] = round(baseline, 4)
    result["price_available"] = True

    # T+0 through T+90
    snapshots = {
        "t0": filing_dt,
        "t30": filing_dt + timedelta(days=30),
        "t60": filing_dt + timedelta(days=60),
        "t90": filing_dt + timedelta(days=90),
    }

    for key, target_dt in snapshots.items():
        price = _next_trading_day_price(history, target_dt)
        if price is not None:
            result[f"price_{key}"] = round(price, 4)
            result[f"return_{key}"] = round((price - baseline) / baseline, 6)

    return result


def enrich_with_prices(incidents: list[dict]) -> list[dict]:
    """
    Add price data to each incident record. Mutates in place and returns the list.
    """
    total = len(incidents)
    for i, incident in enumerate(incidents):
        ticker = incident.get("ticker")
        filing_date = incident.get("filing_date")

        if not ticker or not filing_date:
            continue

        print(f"  [{i+1}/{total}] Fetching prices: {ticker} ({filing_date})")
        price_data = get_price_data(ticker, filing_date)
        incident.update(price_data)

    return incidents
