"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import type { Incident } from "@/lib/types";
import { formatPct } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import RiskBadge from "@/components/RiskBadge";

// Data is passed in via a server component wrapper
export default function IncidentsClient({ incidents }: { incidents: Incident[] }) {
  const [sector, setSector] = useState("all");
  const [capTier, setCapTier] = useState("all");
  const [predicted, setPredicted] = useState("all");
  const [sort, setSort] = useState<"date" | "return_t30" | "alpha_t30">("date");

  const sectors = useMemo(
    () => ["all", ...Array.from(new Set(incidents.map((i) => i.sector).filter(Boolean))).sort()],
    [incidents]
  );

  const filtered = useMemo(() => {
    return incidents
      .filter((i) => sector === "all" || i.sector === sector)
      .filter((i) => capTier === "all" || i.cap_tier === capTier)
      .filter((i) => {
        if (predicted === "all") return true;
        if (predicted === "yes") return i.predicted === true;
        if (predicted === "no") return i.predicted === false;
        if (predicted === "unknown") return i.predicted === null;
        return true;
      })
      .sort((a, b) => {
        if (sort === "date") return (b.filing_date || "").localeCompare(a.filing_date || "");
        if (sort === "return_t30") return (a.return_t30 ?? 0) - (b.return_t30 ?? 0);
        if (sort === "alpha_t30") return (a.alpha_t30 ?? 0) - (b.alpha_t30 ?? 0);
        return 0;
      });
  }, [incidents, sector, capTier, predicted, sort]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">All Incidents</h1>
        <p className="text-slate-400 text-sm mt-1">
          {filtered.length} of {incidents.length} incidents
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          className="bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded px-3 py-1.5"
        >
          {sectors.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "All Sectors" : s}
            </option>
          ))}
        </select>

        <select
          value={capTier}
          onChange={(e) => setCapTier(e.target.value)}
          className="bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded px-3 py-1.5"
        >
          <option value="all">All Cap Tiers</option>
          <option value="large">Large ({">"} $10B)</option>
          <option value="mid">Mid ($2B–$10B)</option>
          <option value="small">Small ({"<"} $2B)</option>
        </select>

        <select
          value={predicted}
          onChange={(e) => setPredicted(e.target.value)}
          className="bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded px-3 py-1.5"
        >
          <option value="all">All Predictions</option>
          <option value="yes">Predicted in 10-K</option>
          <option value="no">Not Predicted</option>
          <option value="unknown">No Analysis</option>
        </select>

        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as typeof sort)}
          className="bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded px-3 py-1.5"
        >
          <option value="date">Sort: Newest First</option>
          <option value="return_t30">Sort: Worst T+30 First</option>
          <option value="alpha_t30">Sort: Worst Alpha First</option>
        </select>
      </div>

      {/* Incident Cards */}
      <div className="space-y-3">
        {filtered.length === 0 ? (
          <p className="text-slate-500">No incidents match these filters.</p>
        ) : (
          filtered.map((inc) => (
            <Link
              key={inc.id}
              href={`/incidents/${inc.id}`}
              className="block bg-slate-900 border border-slate-800 rounded-lg p-4 hover:border-slate-600 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono font-semibold text-orange-400 text-sm">
                      {inc.ticker}
                    </span>
                    <span className="text-white font-medium truncate">{inc.company}</span>
                    <span className="text-xs text-slate-500">{inc.filing_date}</span>
                  </div>
                  <div className="flex gap-2 mt-1.5 flex-wrap">
                    <Badge variant="outline" className="text-xs border-slate-700 text-slate-400">
                      {inc.sector || "Unknown"}
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
                  {inc.incident_description && (
                    <p className="text-xs text-slate-500 mt-2 line-clamp-2">
                      {inc.incident_description}
                    </p>
                  )}
                </div>

                <div className="text-right shrink-0 space-y-2">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                    <span className="text-slate-500">T+0</span>
                    <span className={returnColor(inc.return_t0)}>{formatPct(inc.return_t0)}</span>
                    <span className="text-slate-500">T+30</span>
                    <span className={returnColor(inc.return_t30)}>{formatPct(inc.return_t30)}</span>
                    <span className="text-slate-500">Alpha T+30</span>
                    <span className={returnColor(inc.alpha_t30)}>{formatPct(inc.alpha_t30)}</span>
                  </div>
                  <RiskBadge predicted={inc.predicted} confidence={inc.prediction_confidence} />
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}

function returnColor(val: number | null | undefined): string {
  if (val === null || val === undefined) return "text-slate-500 font-mono";
  return val < 0 ? "text-red-400 font-mono" : "text-emerald-400 font-mono";
}
