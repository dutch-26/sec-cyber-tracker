from __future__ import annotations
"""
sec_fetcher.py — Fetch Item 1.05 Form 8-K material cybersecurity incident filings from SEC EDGAR.

Discovery strategy: iterates the full SEC company_tickers.json (~8K US public companies) and
queries each company's EDGAR submissions history for 8-Ks tagged with item 1.05. This is
authoritative vs. EDGAR's full-text search (EFTS), which has confirmed indexing gaps — e.g.,
AT&T's July 2024 breach filing (73M records) was absent from EFTS despite being in EDGAR.

Runtime: ~20 min for the full historical scan (8K CIKs × SEC rate limit).
Incremental runs pass a more recent start_date and exit each company's history early.
"""

import time
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "sec-cyber-tracker research@example.com"}
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# Rule effective date — Dec 18, 2023 for large/accelerated filers
RULE_START_DATE = "2023-12-18"


def _get(url: str, params: dict = None, retries: int = 3) -> requests.Response:
    """GET with retry and rate-limit courtesy delay."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
            resp.raise_for_status()
            time.sleep(0.11)  # Stay under SEC's 10 req/s limit
            return resp
        except requests.HTTPError:
            if resp.status_code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")


def _ticker_quality(ticker: str) -> int:
    """
    Score a ticker for how likely it is to be the primary common equity.
    Lower score = better. Used to pick the best ticker when a CIK has
    multiple entries (e.g. AT&T: T / TBB / T-PA / T-PC).
    """
    if "-" in ticker:
        return 10   # Preferred share series (dash separator)
    if ticker.endswith("W"):
        return 9    # Warrant
    if ticker.endswith("U"):
        return 8    # Unit
    if ticker.endswith("R"):
        return 7    # Rights
    if len(ticker) > 5:
        return 5    # Unusually long ticker
    return len(ticker)  # Prefer shorter common-stock tickers (T < TBB < GOOGL)


def build_ticker_map() -> dict:
    """
    Returns {cik (zero-padded 10 digits): {"ticker": str, "company": str}}
    from SEC company_tickers.json (~8K US public companies).

    When a CIK has multiple entries (preferred shares, warrants, dual-class),
    picks the entry most likely to be the primary common equity using
    _ticker_quality scoring (lower = better common stock signal).
    """
    data = _get(COMPANY_TICKERS_URL).json()
    ticker_map: dict = {}
    scores: dict = {}   # cik → current best score

    for entry in data.values():
        cik_padded = str(entry["cik_str"]).zfill(10)
        ticker = entry["ticker"]
        score = _ticker_quality(ticker)

        if cik_padded not in ticker_map or score < scores[cik_padded]:
            ticker_map[cik_padded] = {"ticker": ticker, "company": entry["title"]}
            scores[cik_padded] = score

    return ticker_map


def fetch_item105_filings(start_date: str = RULE_START_DATE, ticker_map: dict = None) -> list[dict]:
    """
    Comprehensive discovery: scan every company in the SEC ticker map for Item 1.05
    8-K filings since start_date using the EDGAR submissions API.

    The submissions API is authoritative — it exposes the `items` metadata field
    that EDGAR uses internally to classify filings. EDGAR's full-text search (EFTS)
    has known indexing gaps and misses roughly 50% of actual Item 1.05 disclosures.

    Each company gets exactly one API call. The recent filings array is sorted
    newest-first, so we break as soon as we pass start_date.

    Returns a list of raw filing dicts (not yet enriched with ticker/price data).
    """
    if ticker_map is None:
        ticker_map = build_ticker_map()

    cik_list = sorted(ticker_map.keys())
    total = len(cik_list)
    filings: list[dict] = []
    errors = 0

    print(f"Scanning {total:,} company submission histories for Item 1.05 8-Ks since {start_date}...")

    for idx, cik in enumerate(cik_list):
        if idx > 0 and idx % 500 == 0:
            print(f"  [{idx:,}/{total:,}] {len(filings)} qualifying filings found so far...")

        try:
            data = _get(EDGAR_SUBMISSIONS_URL.format(cik=cik)).json()
        except Exception:
            errors += 1
            continue

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        items_all = recent.get("items", [])
        primary_docs = recent.get("primaryDocument", [])
        report_dates = recent.get("reportDate", [])

        company_name = data.get("name", ticker_map[cik]["company"])

        for i, (form, date, accession) in enumerate(zip(forms, dates, accessions)):
            # recent[] is newest-first — safe to stop once past our start date
            if date < start_date:
                break

            # Only original 8-Ks (not 8-K/A amendments)
            if form != "8-K":
                continue

            # Check items metadata — typically a comma-separated string "1.05,9.01"
            items_raw = items_all[i] if i < len(items_all) else ""
            if isinstance(items_raw, list):
                items_str = ",".join(str(v) for v in items_raw)
            else:
                items_str = str(items_raw)

            if "1.05" not in items_str:
                continue

            filings.append({
                "accession_raw": accession,
                "cik": cik,
                "company_edgar": company_name,
                "filing_date": date,
                "form_type": form,
                "period_of_report": report_dates[i] if i < len(report_dates) else "",
                # Store primary doc for efficient document fetch; stripped before saving
                "_primary_doc": primary_docs[i] if i < len(primary_docs) else "",
            })

    filings.sort(key=lambda x: x["filing_date"], reverse=True)

    if errors:
        print(f"  Warning: {errors} CIKs had submission API errors (skipped)")
    print(f"Total Item 1.05 8-K filings found: {len(filings)}")
    return filings


def fetch_filing_document(accession_raw: str, cik: str, primary_doc: str = None) -> str:
    """
    Fetch the primary 8-K document and return its full text content.

    Uses primary_doc if provided (already known from the submissions API discovery call),
    avoiding a redundant second lookup. Falls back to re-querying submissions API, then
    HTML index parsing.
    """
    accession_nodash = accession_raw.replace("-", "")
    cik_int = int(cik)

    # Method 1: direct URL when primary_doc is already known
    if primary_doc:
        try:
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik_int}/{accession_nodash}/{primary_doc}"
            )
            resp = _get(doc_url)
            return BeautifulSoup(resp.text, "lxml").get_text(separator="\n", strip=True)
        except Exception:
            pass

    # Method 2: re-query submissions API to find primary doc
    try:
        data = _get(EDGAR_SUBMISSIONS_URL.format(cik=cik)).json()
        recent = data.get("filings", {}).get("recent", {})
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])

        for i, acc in enumerate(accessions):
            if acc == accession_raw:
                doc = docs[i] if i < len(docs) else ""
                if doc:
                    doc_url = (
                        f"https://www.sec.gov/Archives/edgar/data/"
                        f"{cik_int}/{accession_nodash}/{doc}"
                    )
                    resp = _get(doc_url)
                    return BeautifulSoup(resp.text, "lxml").get_text(separator="\n", strip=True)
                break
    except Exception:
        pass

    # Method 3: HTML filing index fallback
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_int}/{accession_nodash}/{accession_raw}-index.htm"
    )
    try:
        resp = _get(index_url)
        soup = BeautifulSoup(resp.text, "lxml")
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 4 and cells[3].get_text(strip=True) in ("8-K", "8-K/A"):
                link = cells[2].find("a")
                if link and link.get("href"):
                    doc_url = "https://www.sec.gov" + link["href"]
                    resp = _get(doc_url)
                    return BeautifulSoup(resp.text, "lxml").get_text(separator="\n", strip=True)
    except Exception:
        pass

    return ""


def extract_incident_description(filing_text: str) -> str:
    """
    Extract the Item 1.05 section text from an 8-K document.
    Returns the relevant text block, capped at 2500 chars.
    """
    if not filing_text:
        return ""

    text_lower = filing_text.lower()

    # Find Item 1.05 start (handle non-breaking space variant)
    start = -1
    for marker in ["item 1.05", "item\xa01.05"]:
        idx = text_lower.find(marker)
        if idx != -1:
            start = idx
            break

    if start == -1:
        return ""

    # Find end at next Item heading
    end = len(filing_text)
    for em in ["item 2.", "item 3.", "item 4.", "item 5.",
               "item 6.", "item 7.", "item 8.", "item 9."]:
        idx = text_lower.find(em, start + 50)
        if idx != -1 and idx < end:
            end = idx

    excerpt = filing_text[start:end].strip()
    return excerpt[:2500] if len(excerpt) > 2500 else excerpt


def enrich_filings(filings: list[dict], ticker_map: dict) -> list[dict]:
    """
    Add ticker and incident description to each filing.
    Skips non-resolvable CIKs and non-common-stock instruments.
    """
    enriched = []
    for f in filings:
        cik = f["cik"]
        ticker_info = ticker_map.get(cik)

        if not ticker_info:
            # Fuzzy match for inconsistent zero-padding
            cik_stripped = str(int(cik))
            for k, v in ticker_map.items():
                if k.lstrip("0") == cik_stripped:
                    ticker_info = v
                    break

        if not ticker_info:
            print(f"  No ticker for CIK {cik} ({f['company_edgar']}) — skipping")
            continue

        ticker = ticker_info["ticker"]
        # Skip warrants (W suffix), preferred shares (- separator), other non-common instruments
        if "-" in ticker or ticker.endswith("W") or ticker.endswith("U") or len(ticker) > 5:
            print(f"  Skipping non-common ticker {ticker} — likely preferred/warrant")
            continue

        f["ticker"] = ticker
        f["company"] = ticker_info["company"]

        # Pop internal field before saving
        primary_doc = f.pop("_primary_doc", None)

        print(f"  Fetching filing text: {ticker} ({f['filing_date']})")
        try:
            filing_text = fetch_filing_document(f["accession_raw"], cik, primary_doc=primary_doc)
            f["incident_description"] = extract_incident_description(filing_text)
        except Exception as e:
            print(f"    Warning: could not fetch filing text: {e}")
            f["incident_description"] = ""

        f["sec_url"] = (
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            f"&CIK={cik}&type=8-K&dateb=&owner=include&count=10"
        )

        enriched.append(f)

    return enriched


def fetch_all_incidents(start_date: str = RULE_START_DATE) -> list[dict]:
    """Main entry point. Returns enriched list of Item 1.05 incidents."""
    ticker_map = build_ticker_map()
    print(f"Loaded ticker map: {len(ticker_map)} companies")

    filings = fetch_item105_filings(start_date, ticker_map)
    enriched = enrich_filings(filings, ticker_map)

    print(f"Enriched {len(enriched)} incidents with ticker + description")
    return enriched
