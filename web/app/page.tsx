import Link from "next/link";
import { getAllIncidents, getMeta, computeStats, formatPct } from "@/lib/data";
import { Badge } from "@/components/ui/badge";
import RiskBadge from "@/components/RiskBadge";

export const revalidate = 86400; // 24-hour ISR

export default function HomePage() {
  const incidents = getAllIncidents();
  const meta = getMeta();
  const stats = computeStats(incidents);

  const recent = incidents.slice(0, 5);

  const sectorEntries = Object.entries(stats.bySector).sort((a, b) => b[1] - a[1]);

  return (
    <div className="space-y-12">
      {/* Hero */}
      <div className="space-y-3">
        <h1 className="text-3xl font-bold tracking-tight text-white">
          SEC Material Cybersecurity Incident Tracker
        </h1>
        <p className="text-slate-400 max-w-2xl">
          Every Form 8-K Item 1.05 disclosure since the SEC cybersecurity rule took effect
          (December 18, 2023) — with stock price performance vs. sector peers and analysis of
          whether the company predicted the risk in their most recent 10-K.
        </p>
        {meta.last_updated && (
          <p className="text-xs text-slate-600">
            Last updated: {new Date(meta.last_updated).toLocaleDateString("en-US", { dateStyle: "long" })}
          </p>
        )}
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Incidents" value={String(incidents.length)} />
        <StatCard
          label="Median T+30 Return"
          value={formatPct(stats.median)}
          valueClass={
            stats.median === null ? "" : stats.median < 0 ? "text-red-400" : "text-emerald-400"
          }
        />
        <StatCard
          label="Avg T+30 Return"
          value={formatPct(stats.mean)}
          valueClass={
            stats.mean === null ? "" : stats.mean < 0 ? "text-red-400" : "text-emerald-400"
          }
        />
        <StatCard
          label="Risk Predicted in 10-K"
          value={
            stats.predictedPct !== null
              ? `${Math.round(stats.predictedPct * 100)}%`
              : "N/A"
          }
          sub={stats.withAnalysis > 0 ? `${stats.predicted} of ${stats.withAnalysis} analyzed` : ""}
        />
      </div>

      <div className="grid md:grid-cols-3 gap-8">
        {/* Recent Incidents */}
        <div className="md:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Recent Disclosures</h2>
            <Link href="/incidents" className="text-sm text-blue-400 hover:text-blue-300">
              View all →
            </Link>
          </div>
          <div className="space-y-3">
            {recent.length === 0 ? (
              <p className="text-slate-500 text-sm">
                No incidents yet — run the pipeline to populate data.
              </p>
            ) : (
              recent.map((inc) => (
                <Link
                  key={inc.id}
                  href={`/incidents/${inc.id}`}
                  className="block bg-slate-900 border border-slate-800 rounded-lg p-4 hover:border-slate-600 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono font-semibold text-orange-400 text-sm">
                          {inc.ticker}
                        </span>
                        <span className="text-white text-sm truncate">{inc.company}</span>
                      </div>
                      <div className="flex gap-2 mt-1 flex-wrap">
                        <Badge variant="outline" className="text-xs border-slate-700 text-slate-400">
                          {inc.sector}
                        </Badge>
                        <Badge variant="outline" className="text-xs border-slate-700 text-slate-400 capitalize">
                          {inc.cap_tier}
                        </Badge>
                        {inc.incident_type && (
                          <Badge variant="outline" className="text-xs border-slate-700 text-slate-400">
                            {inc.incident_type}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="text-right shrink-0 space-y-1">
                      <div
                        className={`text-sm font-mono font-semibold ${
                          inc.return_t30 === null
                            ? "text-slate-500"
                            : inc.return_t30 < 0
                            ? "text-red-400"
                            : "text-emerald-400"
                        }`}
                      >
                        T+30: {formatPct(inc.return_t30)}
                      </div>
                      <RiskBadge predicted={inc.predicted} confidence={inc.prediction_confidence} />
                    </div>
                  </div>
                  <p className="text-xs text-slate-600 mt-1">{inc.filing_date}</p>
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Sidebar: By Sector */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white">Incidents by Sector</h2>
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
            {sectorEntries.length === 0 ? (
              <p className="text-slate-500 text-sm">No data yet.</p>
            ) : (
              sectorEntries.map(([sector, count]) => (
                <div key={sector} className="flex items-center justify-between">
                  <span className="text-sm text-slate-300 truncate">{sector}</span>
                  <div className="flex items-center gap-2">
                    <div
                      className="h-2 bg-orange-500 rounded-full"
                      style={{ width: `${Math.max(8, (count / incidents.length) * 80)}px` }}
                    />
                    <span className="text-sm text-slate-400 w-4 text-right">{count}</span>
                  </div>
                </div>
              ))
            )}
          </div>

          <h2 className="text-lg font-semibold text-white mt-6">By Market Cap Tier</h2>
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
            {["large", "mid", "small", "unknown"].map((tier) => (
              <div key={tier} className="flex items-center justify-between">
                <span className="text-sm text-slate-300 capitalize">{tier}</span>
                <span className="text-sm text-slate-400">{stats.byCapTier[tier] || 0}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  valueClass = "text-white",
  sub,
}: {
  label: string;
  value: string;
  valueClass?: string;
  sub?: string;
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
      <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-bold mt-1 font-mono ${valueClass}`}>{value}</p>
      {sub && <p className="text-xs text-slate-600 mt-1">{sub}</p>}
    </div>
  );
}
