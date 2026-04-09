"""
tenk_analyzer.py — Find each company's most recent 10-K before a given incident date,
extract Item 1A (Risk Factors) text, and use Claude to analyze whether the incident
risk type was predicted in the filing.

Claude prompt design:
  - Input: Item 1A text + incident description
  - Output (JSON): risk_types_disclosed[], incident_type, predicted (bool),
    confidence (0-1), analysis (1-2 sentences)
"""

import json
import re
import time
from datetime import datetime

import anthropic
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "sec-cyber-tracker research@example.com"}
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_BASE = "https://www.sec.gov"

RISK_TYPES = [
    "ransomware",
    "data breach / exfiltration",
    "nation-state / APT",
    "third-party / supply chain",
    "insider threat",
    "DDoS / availability",
    "OT / ICS / operational",
    "credential compromise / phishing",
    "zero-day / vulnerability exploitation",
    "business email compromise",
    "other",
]

ANALYSIS_PROMPT = """You are a cybersecurity and securities law analyst. Your task is to determine whether a company's 10-K Item 1A (Risk Factors) adequately predicted the type of cybersecurity incident they later disclosed via SEC Form 8-K.

## Item 1A Risk Factors Text (from most recent 10-K prior to incident):
{item_1a_text}

## Material Cybersecurity Incident (from Form 8-K Item 1.05):
{incident_description}

## Instructions:
Analyze the above and respond with a JSON object containing ONLY these fields:

1. "risk_types_disclosed": array of risk type labels from this list that appear meaningfully in Item 1A:
   {risk_types}

2. "incident_type": single string — classify the 8-K incident into one of those same labels

3. "predicted": boolean — true if the incident type is meaningfully covered in Item 1A risk disclosures (not just generic boilerplate), false otherwise

4. "confidence": float 0.0–1.0 — your confidence in the predicted assessment
   - 0.9–1.0: explicit, specific language matching the incident type
   - 0.6–0.8: general language that covers the incident category
   - 0.3–0.5: tangential or boilerplate coverage only
   - 0.0–0.2: no meaningful coverage

5. "analysis": string, 1–2 sentences explaining your reasoning, citing specific language from Item 1A if predicted=true

Respond with ONLY valid JSON. No markdown, no preamble."""


def _get(url: str, retries: int = 3) -> requests.Response:
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            time.sleep(0.15)
            return resp
        except requests.HTTPError as e:
            if resp.status_code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"Failed after {retries} attempts: {url}")


def find_most_recent_10k(cik: str, before_date: str) -> dict | None:
    """
    Find the most recent 10-K (or 10-K/A) filed before before_date for a given CIK.
    Returns {"accession": str, "filing_date": str, "primary_doc": str} or None.
    """
    try:
        url = SUBMISSIONS_URL.format(cik=cik)
        data = _get(url).json()
    except Exception as e:
        print(f"    Could not fetch submissions for CIK {cik}: {e}")
        return None

    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])
    primary_docs = filings.get("primaryDocument", [])

    cutoff = datetime.strptime(before_date, "%Y-%m-%d")
    best = None

    for form, date_str, accession, primary_doc in zip(forms, dates, accessions, primary_docs):
        if form not in ("10-K", "10-K/A"):
            continue
        try:
            filing_dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if filing_dt >= cutoff:
            continue
        if best is None or filing_dt > datetime.strptime(best["filing_date"], "%Y-%m-%d"):
            best = {
                "accession": accession,
                "filing_date": date_str,
                "primary_doc": primary_doc,
                "cik": cik,
            }

    return best


def fetch_item_1a_text(tenk_info: dict) -> str:
    """
    Fetch the 10-K document and extract Item 1A (Risk Factors) text.
    Returns extracted text, capped at 12000 chars (Claude context efficiency).
    """
    cik = tenk_info["cik"]
    accession = tenk_info["accession"]
    primary_doc = tenk_info["primary_doc"]

    accession_nodash = accession.replace("-", "")
    cik_int = int(cik)

    doc_url = f"{EDGAR_BASE}/Archives/edgar/data/{cik_int}/{accession_nodash}/{primary_doc}"

    try:
        resp = _get(doc_url)
    except Exception as e:
        print(f"    Could not fetch 10-K document: {e}")
        return ""

    soup = BeautifulSoup(resp.content, "lxml")
    text = soup.get_text(separator="\n", strip=True)

    # Extract Item 1A section
    text_lower = text.lower()

    # Find Item 1A start
    start = -1
    for pattern in [r"item\s+1a[\.\s]", r"item\s+1a\."]:
        match = re.search(pattern, text_lower)
        if match:
            start = match.start()
            break

    if start == -1:
        # Fallback: just return first 12000 chars of full text
        return text[:12000]

    # Find Item 1B or Item 2 to end the section
    end = len(text)
    for pattern in [r"item\s+1b[\.\s]", r"item\s+2[\.\s]"]:
        match = re.search(pattern, text_lower[start + 100:])
        if match:
            end = start + 100 + match.start()
            break

    item_1a = text[start:end].strip()

    # Cap at 12000 chars
    return item_1a[:12000] if len(item_1a) > 12000 else item_1a


def analyze_with_claude(item_1a_text: str, incident_description: str, client: anthropic.Anthropic) -> dict:
    """
    Send Item 1A text + incident description to Claude for risk prediction analysis.
    Returns structured dict with analysis results.
    """
    default = {
        "risk_types_disclosed": [],
        "incident_type": "unknown",
        "predicted": False,
        "confidence": 0.0,
        "analysis": "Analysis unavailable.",
    }

    if not item_1a_text or not incident_description:
        return default

    prompt = ANALYSIS_PROMPT.format(
        item_1a_text=item_1a_text[:10000],  # Safety cap
        incident_description=incident_description[:1500],
        risk_types=json.dumps(RISK_TYPES),
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Strip any markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        result = json.loads(raw)

        # Validate and normalize
        return {
            "risk_types_disclosed": result.get("risk_types_disclosed", []),
            "incident_type": str(result.get("incident_type", "unknown")),
            "predicted": bool(result.get("predicted", False)),
            "prediction_confidence": float(result.get("confidence", 0.0)),
            "prediction_analysis": str(result.get("analysis", "")),
        }
    except json.JSONDecodeError as e:
        print(f"    Claude returned invalid JSON: {e}")
        return default
    except Exception as e:
        print(f"    Claude API error: {e}")
        return default


def enrich_with_tenk_analysis(incidents: list[dict], anthropic_api_key: str) -> list[dict]:
    """
    For each incident, find the most recent 10-K, extract Item 1A, and run Claude analysis.
    """
    client = anthropic.Anthropic(api_key=anthropic_api_key)
    total = len(incidents)

    for i, incident in enumerate(incidents):
        cik = incident.get("cik")
        filing_date = incident.get("filing_date")
        ticker = incident.get("ticker", "")

        if not cik or not filing_date:
            continue

        print(f"  [{i+1}/{total}] 10-K analysis: {ticker} ({filing_date})")

        # Find most recent 10-K before incident
        tenk = find_most_recent_10k(cik, filing_date)
        if not tenk:
            print(f"    No 10-K found for {ticker}")
            incident["tenk_filing_date"] = None
            incident["tenk_accession"] = None
            incident["tenk_url"] = None
            incident["risk_types_disclosed"] = []
            incident["incident_type"] = "unknown"
            incident["predicted"] = None
            incident["prediction_confidence"] = None
            incident["prediction_analysis"] = "No 10-K found prior to incident date."
            continue

        incident["tenk_filing_date"] = tenk["filing_date"]
        incident["tenk_accession"] = tenk["accession"]
        accession_nodash = tenk["accession"].replace("-", "")
        incident["tenk_url"] = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession_nodash}/{tenk['primary_doc']}"
        )

        # Extract Item 1A
        print(f"    Fetching 10-K: {tenk['filing_date']}")
        item_1a = fetch_item_1a_text(tenk)

        if not item_1a:
            print(f"    Could not extract Item 1A for {ticker}")
            incident["risk_types_disclosed"] = []
            incident["incident_type"] = "unknown"
            incident["predicted"] = None
            incident["prediction_confidence"] = None
            incident["prediction_analysis"] = "Could not extract Item 1A text."
            continue

        # Claude analysis
        print(f"    Running Claude analysis ({len(item_1a)} chars Item 1A)...")
        analysis = analyze_with_claude(item_1a, incident.get("incident_description", ""), client)
        incident.update(analysis)

        # Brief pause between Claude calls
        time.sleep(0.5)

    return incidents
