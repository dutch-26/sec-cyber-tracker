export interface Incident {
  id: string;
  company: string;
  ticker: string;
  cik: string;
  filing_date: string;
  accession_raw: string;
  incident_description: string;
  incident_type: string | null;
  sector: string;
  cap_tier: "small" | "mid" | "large" | "unknown";
  market_cap_usd: number | null;
  peer_etf: string;
  price_available: boolean;
  price_baseline: number | null;
  price_t0: number | null;
  price_t30: number | null;
  price_t60: number | null;
  price_t90: number | null;
  return_t0: number | null;
  return_t30: number | null;
  return_t60: number | null;
  return_t90: number | null;
  peer_return_t0: number | null;
  peer_return_t30: number | null;
  peer_return_t60: number | null;
  peer_return_t90: number | null;
  alpha_t0: number | null;
  alpha_t30: number | null;
  alpha_t60: number | null;
  alpha_t90: number | null;
  tenk_filing_date: string | null;
  tenk_accession: string | null;
  tenk_url: string | null;
  risk_types_disclosed: string[];
  predicted: boolean | null;
  prediction_confidence: number | null;
  prediction_analysis: string | null;
  sec_url: string;
}

export interface Meta {
  last_updated: string | null;
  total_incidents: number;
}

export function formatPct(val: number | null, decimals = 1): string {
  if (val === null || val === undefined) return "N/A";
  return `${val >= 0 ? "+" : ""}${(val * 100).toFixed(decimals)}%`;
}

export function formatCap(val: number | null): string {
  if (!val) return "N/A";
  if (val >= 1e12) return `$${(val / 1e12).toFixed(1)}T`;
  if (val >= 1e9) return `$${(val / 1e9).toFixed(1)}B`;
  if (val >= 1e6) return `$${(val / 1e6).toFixed(0)}M`;
  return `$${val.toLocaleString()}`;
}

export function computeStats(incidents: Incident[]) {
  const withReturns = incidents.filter((i) => i.return_t30 !== null);
  const returns = withReturns.map((i) => i.return_t30!).sort((a, b) => a - b);
  const median = returns.length > 0 ? returns[Math.floor(returns.length / 2)] : null;
  const mean =
    returns.length > 0 ? returns.reduce((a, b) => a + b, 0) / returns.length : null;

  const withAnalysis = incidents.filter((i) => i.predicted !== null);
  const predicted = withAnalysis.filter((i) => i.predicted === true).length;
  const predictedPct =
    withAnalysis.length > 0 ? predicted / withAnalysis.length : null;

  const bySector = incidents.reduce<Record<string, number>>((acc, i) => {
    const s = i.sector || "Unknown";
    acc[s] = (acc[s] || 0) + 1;
    return acc;
  }, {});

  const byCapTier = incidents.reduce<Record<string, number>>((acc, i) => {
    const t = i.cap_tier || "unknown";
    acc[t] = (acc[t] || 0) + 1;
    return acc;
  }, {});

  return { median, mean, predictedPct, predicted, withAnalysis: withAnalysis.length, bySector, byCapTier };
}
