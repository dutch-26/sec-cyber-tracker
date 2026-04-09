"""
main.py — Orchestrates the full SEC Cyber Incident Tracker data pipeline.

Pipeline stages:
  1. Fetch all Item 1.05 8-K filings from EDGAR
  2. Enrich with stock price data (yfinance)
  3. Enrich with peer group classification and ETF returns
  4. Enrich with 10-K Item 1A risk analysis (Claude API)
  5. Write output to data/incidents.json and data/meta.json

Idempotent: existing incidents (matched by accession number) are preserved
unless --refresh flag is passed.

Usage:
  python pipeline/main.py                  # incremental update
  python pipeline/main.py --refresh        # full refresh (re-fetch all)
  python pipeline/main.py --skip-claude    # skip Claude analysis (faster testing)
  ANTHROPIC_API_KEY=sk-... python pipeline/main.py
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent))

from sec_fetcher import fetch_all_incidents
from stock_tracker import enrich_with_prices
from peer_comparator import enrich_with_peers
from tenk_analyzer import enrich_with_tenk_analysis

DATA_DIR = Path(__file__).parent.parent / "data"
INCIDENTS_FILE = DATA_DIR / "incidents.json"
META_FILE = DATA_DIR / "meta.json"


def load_existing_incidents() -> tuple[list[dict], set[str]]:
    """Load existing incidents.json, return (records, set of accession numbers)."""
    if not INCIDENTS_FILE.exists():
        return [], set()
    with open(INCIDENTS_FILE) as f:
        records = json.load(f)
    existing_accessions = {r["accession_raw"] for r in records if r.get("accession_raw")}
    return records, existing_accessions


def save_incidents(incidents: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(INCIDENTS_FILE, "w") as f:
        json.dump(incidents, f, indent=2, default=str)

    meta = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_incidents": len(incidents),
    }
    with open(META_FILE, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nSaved {len(incidents)} incidents to {INCIDENTS_FILE}")


def assign_ids(incidents: list[dict]) -> list[dict]:
    """Assign a stable UUID to any incident that doesn't have one."""
    for incident in incidents:
        if not incident.get("id"):
            incident["id"] = str(uuid.uuid4())
    return incidents


def summarize(incidents: list[dict]) -> None:
    """Print a brief summary of the dataset."""
    total = len(incidents)
    with_prices = sum(1 for i in incidents if i.get("price_available"))
    with_analysis = sum(1 for i in incidents if i.get("predicted") is not None)
    predicted = sum(1 for i in incidents if i.get("predicted") is True)

    returns_t30 = [i["return_t30"] for i in incidents if i.get("return_t30") is not None]
    median_t30 = (
        sorted(returns_t30)[len(returns_t30) // 2] if returns_t30 else None
    )

    print("\n" + "=" * 50)
    print("PIPELINE SUMMARY")
    print("=" * 50)
    print(f"  Total incidents:         {total}")
    print(f"  With price data:         {with_prices}")
    print(f"  With Claude analysis:    {with_analysis}")
    print(f"  Risk predicted in 10-K:  {predicted} / {with_analysis}")
    if median_t30 is not None:
        print(f"  Median T+30 return:      {median_t30:+.2%}")
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(description="SEC Cyber Incident Tracker pipeline")
    parser.add_argument("--refresh", action="store_true", help="Full refresh — re-fetch all incidents")
    parser.add_argument("--skip-claude", action="store_true", help="Skip Claude 10-K analysis")
    parser.add_argument("--limit", type=int, default=None, help="Process only N incidents (for testing)")
    args = parser.parse_args()

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not args.skip_claude and not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("Run with --skip-claude to skip 10-K analysis, or set the key.")
        sys.exit(1)

    # Stage 1: Fetch
    print("\n[Stage 1] Fetching Item 1.05 8-K filings from EDGAR...")
    new_incidents = fetch_all_incidents()

    # Load existing and deduplicate
    existing_incidents, existing_accessions = load_existing_incidents()

    if args.refresh:
        print("[Refresh mode] Re-processing all incidents")
        to_process = new_incidents
        base_incidents = []
    else:
        to_process = [i for i in new_incidents if i["accession_raw"] not in existing_accessions]
        base_incidents = existing_incidents
        print(f"[Incremental] {len(to_process)} new incidents to process (skipping {len(existing_incidents)} existing)")

    if args.limit:
        to_process = to_process[:args.limit]
        print(f"[Limit] Processing only first {args.limit} incidents")

    if not to_process:
        print("No new incidents to process. Dataset is up to date.")
        save_incidents(existing_incidents)
        summarize(existing_incidents)
        return

    # Assign IDs
    to_process = assign_ids(to_process)

    # Stage 2: Stock prices
    print(f"\n[Stage 2] Fetching stock prices for {len(to_process)} incidents...")
    enrich_with_prices(to_process)

    # Stage 3: Peer group
    print(f"\n[Stage 3] Classifying sectors and computing peer returns...")
    enrich_with_peers(to_process)

    # Stage 4: 10-K analysis
    if not args.skip_claude:
        print(f"\n[Stage 4] Running 10-K Item 1A analysis with Claude...")
        enrich_with_tenk_analysis(to_process, anthropic_key)
    else:
        print("\n[Stage 4] Skipping Claude analysis (--skip-claude flag set)")
        for incident in to_process:
            incident.setdefault("risk_types_disclosed", [])
            incident.setdefault("incident_type", None)
            incident.setdefault("predicted", None)
            incident.setdefault("prediction_confidence", None)
            incident.setdefault("prediction_analysis", None)
            incident.setdefault("tenk_filing_date", None)
            incident.setdefault("tenk_url", None)

    # Stage 5: Save
    all_incidents = base_incidents + to_process
    # Sort by filing date descending
    all_incidents.sort(key=lambda x: x.get("filing_date", ""), reverse=True)

    print(f"\n[Stage 5] Saving {len(all_incidents)} total incidents...")
    save_incidents(all_incidents)
    summarize(all_incidents)


if __name__ == "__main__":
    main()
