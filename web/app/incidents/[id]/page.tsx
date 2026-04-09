import { notFound } from "next/navigation";
import Link from "next/link";
import { getAllIncidents, getIncidentById, formatPct, formatCap } from "@/lib/data";
import { Badge } from "@/components/ui/badge";
import RiskBadge from "@/components/RiskBadge";
import PriceChart from "@/components/PriceChart";
import AlphaBar from "@/components/AlphaBar";

export const revalidate = 86400;

export async function generateStaticParams() {
  const incidents = getAllIncidents();
  return incidents.map((i) => ({ id: i.id }));
}

export default function IncidentDetailPage({ params }: { params: { id: string } }) {
  const incident = getIncidentById(params.id);
  if (!incident) notFound();

  const {
    company, ticker, sector, cap_tier, market_cap_usd, filing_date,
    incident_description, incident_type, peer_etf,
    price_baseline, price_t0, price_t30, price_t60, price_t90,
    return_t0, return_t30, return_t60, return_t90,
    alpha_t0, alpha_t30, alpha_t60, alpha_t90,
    tenk_filing_date, tenk_url, risk_types_disclosed,
    predicted, prediction_confidence, prediction_analysis,
    sec_url, accession_raw,
  } = incident;

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Breadcrumb */}
      <nav className="text-sm text-slate-500">
        <Link href="/incidents" className="hover:text-slate-300">← All Incidents</Link>
      </nav>

      {/* Header */}
      <div className="space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-3xl font-bold font-mono text-orange-400">{ticker}</span>
          <h1 className="text-2xl font-bold text-white">{company}</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="border-slate-700 text-slate-300">{sector}</Badge>
          <Badge variant="outline" className="border-slate-700 text-slate-300 capitalize">{cap_tier} cap</Badge>
          <Badge variant="outline" className="border-slate-700 text-slate-300">{formatCap(market_cap_usd)}</Badge>
          {incident_type && (
            <Badge variant="outline" className="border-slate-700 text-slate-300">{incident_type}</Badge>
          )}
        </div>
        <p className="text-sm text-slate-500">
          8-K filed: <span className="text-slate-300">{filing_date}</span>
          {" · "}
          <a href={sec_url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300">
            View on EDGAR ↗
          </a>
          {accession_raw && (
            <span className="ml-2 text-slate-600 font-mono text-xs">{accession_raw}</span>
          )}
        </p>
      </div>

      {/* Incident Description */}
      {incident_description && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-2">Incident Description (Item 1.05)</h2>
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 text-sm text-slate-300 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto font-mono">
            {incident_description}
          </div>
        </section>
      )}

      {/* Price Performance */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-1">Stock Price Performance</h2>
        <p className="text-xs text-slate-500 mb-4">
          Baseline: ${price_baseline?.toFixed(2) ?? "N/A"} (T-1 close) · Peer proxy: {peer_etf} sector ETF
        </p>

        {/* Snapshot table */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {[
            { label: "Filing Day (T+0)", price: price_t0, ret: return_t0, alpha: alpha_t0 },
            { label: "T+30 Days", price: price_t30, ret: return_t30, alpha: alpha_t30 },
            { label: "T+60 Days", price: price_t60, ret: return_t60, alpha: alpha_t60 },
            { label: "T+90 Days", price: price_t90, ret: return_t90, alpha: alpha_t90 },
          ].map(({ label, price, ret, alpha }) => (
            <div key={label} className="bg-slate-900 border border-slate-800 rounded-lg p-3">
              <p className="text-xs text-slate-500">{label}</p>
              <p className="font-mono text-white mt-0.5">${price?.toFixed(2) ?? "—"}</p>
              <p className={`text-sm font-mono font-semibold ${ret === null ? "text-slate-500" : ret < 0 ? "text-red-400" : "text-emerald-400"}`}>
                {formatPct(ret)}
              </p>
              <p className={`text-xs font-mono ${alpha === null ? "text-slate-600" : alpha < 0 ? "text-red-500" : "text-emerald-500"}`}>
                α {formatPct(alpha)}
              </p>
            </div>
          ))}
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
          <p className="text-xs text-slate-500 mb-3 uppercase tracking-wide">Return vs. {peer_etf} Sector ETF</p>
          <PriceChart incident={incident} />
        </div>
      </section>

      {/* Alpha vs Peers */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-1">Alpha vs. Sector Peers</h2>
        <p className="text-xs text-slate-500 mb-4">
          Company return minus {peer_etf} ETF return. Negative = underperformed peers.
        </p>
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
          <AlphaBar incident={incident} />
        </div>
      </section>

      {/* 10-K Risk Analysis */}
      <section>
        <div className="flex items-center gap-3 mb-3">
          <h2 className="text-lg font-semibold text-white">10-K Item 1A Risk Analysis</h2>
          <RiskBadge predicted={predicted} confidence={prediction_confidence} />
        </div>

        {tenk_filing_date ? (
          <div className="space-y-4">
            <p className="text-sm text-slate-400">
              Most recent 10-K before incident:{" "}
              <span className="text-slate-200">{tenk_filing_date}</span>
              {tenk_url && (
                <>
                  {" · "}
                  <a href={tenk_url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300">
                    View 10-K ↗
                  </a>
                </>
              )}
            </p>

            {risk_types_disclosed?.length > 0 && (
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Risk Types Disclosed in Item 1A</p>
                <div className="flex flex-wrap gap-2">
                  {risk_types_disclosed.map((rt) => (
                    <Badge key={rt} className="bg-slate-700 text-slate-200">{rt}</Badge>
                  ))}
                </div>
              </div>
            )}

            {incident_type && (
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Actual Incident Type</p>
                <Badge className="bg-orange-900 text-orange-200">{incident_type}</Badge>
              </div>
            )}

            {prediction_analysis && (
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Claude Analysis</p>
                <p className="text-sm text-slate-300 leading-relaxed">{prediction_analysis}</p>
                {prediction_confidence !== null && (
                  <p className="text-xs text-slate-600 mt-2">
                    Confidence: {Math.round((prediction_confidence ?? 0) * 100)}%
                  </p>
                )}
              </div>
            )}
          </div>
        ) : (
          <p className="text-slate-500 text-sm">No 10-K found prior to incident date.</p>
        )}
      </section>
    </div>
  );
}
