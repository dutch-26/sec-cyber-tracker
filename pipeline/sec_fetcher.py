"""
sec_fetcher.py — Fetch Item 1.05 Form 8-K material cybersecurity incident filings from SEC EDGAR.

Queries the EDGAR full-text search API for all Item 1.05 filings since Dec 18, 2023
(the effective date of the SEC cybersecurity disclosure rule), resolves company tickers,
and extracts incident description text.
"""

import time
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "sec-cyber-tracker research@example.com"}  # SEC requires a User-Agent
EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_FILING_BASE = "https://www.sec.gov/Archives/edgar"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# Rule effective date
RULE_START_DATE = "2023-12-18"


def _get(url: str, params: dict = None, retries: int = 3) -> requests.Response:
    """GET with retry and rate-limit courtesy delay."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            time.sleep(0.15)  # Stay well under SEC's 10 req/s limit
            return resp
        except requests.HTTPError as e:
            if resp.status_code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")


def build_ticker_map() -> dict:
    """
    Returns {cik_str (zero-padded 10 digits): ticker} from SEC company_tickers.json.
    Also returns a reverse map for convenience.
    """
    data = _get(COMPANY_TICKERS_URL).json()
    # SEC format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    ticker_map = {}
    for entry in data.values():
        cik_padded = str(entry["cik_str"]).zfill(10)
        ticker_map[cik_padded] = {
            "ticker": entry["ticker"],
            "company": entry["title"],
        }
    return ticker_map


def fetch_item105_filings(start_date: str = RULE_START_DATE) -> list[dict]:
    """
    Fetch all Item 1.05 8-K filings from EDGAR full-text search.
    Returns a list of raw filing metadata dicts.
    """
    filings = []
    from_index = 0
    page_size = 100

    print(f"Fetching Item 1.05 8-K filings from {start_date}...")

    while True:
        params = {
            "q": '"Item 1.05"',
            "forms": "8-K",
            "dateRange": "custom",
            "startdt": start_date,
            "from": from_index,
            "hits.hits.total.value": page_size,
        }
        resp = _get(EDGAR_SEARCH_URL, params=params)
        data = resp.json()

        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break

        for hit in hits:
            source = hit.get("_source", {})
            filings.append({
                "accession": source.get("file_date", "").replace("-", "") + "-" + hit.get("_id", ""),
                "accession_raw": hit.get("_id", ""),
                "cik": str(source.get("entity_id", "")).zfill(10),
                "company_edgar": source.get("display_names", [""])[0] if source.get("display_names") else "",
                "filing_date": source.get("file_date", ""),
                "form_type": source.get("form_type", ""),
                "file_url": source.get("file_url", ""),
                "period_of_report": source.get("period_of_report", ""),
            })

        from_index += len(hits)
        total = data.get("hits", {}).get("total", {}).get("value", 0)
        print(f"  Fetched {from_index}/{total} filings...")

        if from_index >= total:
            break

    print(f"Total Item 1.05 8-K filings found: {len(filings)}")
    return filings


def fetch_filing_document(accession_raw: str, cik: str) -> str:
    """
    Given a raw accession number (e.g. '0001234567-24-000001') and CIK,
    fetch the primary 8-K document and return its text content.
    """
    # Build filing index URL
    accession_nodash = accession_raw.replace("-", "")
    index_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=8-K&dateb=&owner=include&count=40"

    # Direct approach: fetch the filing index
    index_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/{accession_raw}-index.htm"
    try:
        resp = _get(index_url)
        soup = BeautifulSoup(resp.text, "lxml")

        # Find the primary document link (8-K form)
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 4:
                doc_type = cells[3].get_text(strip=True)
                if doc_type in ("8-K", "8-K/A"):
                    link = cells[2].find("a")
                    if link and link.get("href"):
                        doc_url = "https://www.sec.gov" + link["href"]
                        doc_resp = _get(doc_url)
                        doc_soup = BeautifulSoup(doc_resp.text, "lxml")
                        return doc_soup.get_text(separator="\n", strip=True)
    except Exception:
        pass

    return ""


def extract_incident_description(filing_text: str) -> str:
    """
    Extract the Item 1.05 section text from an 8-K document.
    Returns the relevant text block (up to ~2000 chars).
    """
    if not filing_text:
        return ""

    text_lower = filing_text.lower()

    # Find Item 1.05 section
    markers = ["item 1.05", "item\xa01.05"]
    start = -1
    for marker in markers:
        idx = text_lower.find(marker)
        if idx != -1:
            start = idx
            break

    if start == -1:
        return ""

    # Find end: next Item heading or reasonable cutoff
    end_markers = ["item 2.", "item 3.", "item 4.", "item 5.", "item 6.", "item 7.", "item 8.", "item 9."]
    end = len(filing_text)
    for em in end_markers:
        idx = text_lower.find(em, start + 50)
        if idx != -1 and idx < end:
            end = idx

    excerpt = filing_text[start:end].strip()
    # Cap at 2500 chars for storage
    return excerpt[:2500] if len(excerpt) > 2500 else excerpt


def enrich_filings(filings: list[dict], ticker_map: dict) -> list[dict]:
    """
    Add ticker and incident description to each filing record.
    Skips filings where no ticker can be resolved (foreign privates, etc.).
    """
    enriched = []
    for f in filings:
        cik = f["cik"]
        ticker_info = ticker_map.get(cik)

        if not ticker_info:
            # Try without zero-padding (some CIKs are inconsistent)
            cik_int = str(int(cik))
            for k, v in ticker_map.items():
                if k.lstrip("0") == cik_int:
                    ticker_info = v
                    break

        if not ticker_info:
            print(f"  No ticker for CIK {cik} ({f['company_edgar']}) — skipping")
            continue

        f["ticker"] = ticker_info["ticker"]
        f["company"] = ticker_info["company"]

        # Fetch incident description
        print(f"  Fetching filing text: {f['ticker']} ({f['filing_date']})")
        try:
            filing_text = fetch_filing_document(f["accession_raw"], cik)
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

    filings = fetch_item105_filings(start_date)
    enriched = enrich_filings(filings, ticker_map)

    print(f"Enriched {len(enriched)} incidents with ticker + description")
    return enriched
