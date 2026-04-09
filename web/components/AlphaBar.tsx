"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { Incident } from "@/lib/types";

interface Props {
  incident: Incident;
}

export default function AlphaBar({ incident }: Props) {
  const data = [
    { label: "T+0", alpha: incident.alpha_t0 !== null ? +(incident.alpha_t0 * 100).toFixed(2) : null },
    { label: "T+30", alpha: incident.alpha_t30 !== null ? +(incident.alpha_t30 * 100).toFixed(2) : null },
    { label: "T+60", alpha: incident.alpha_t60 !== null ? +(incident.alpha_t60 * 100).toFixed(2) : null },
    { label: "T+90", alpha: incident.alpha_t90 !== null ? +(incident.alpha_t90 * 100).toFixed(2) : null },
  ].filter((d) => d.alpha !== null);

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#94a3b8" }} />
        <YAxis
          tickFormatter={(v) => `${v > 0 ? "+" : ""}${v}%`}
          tick={{ fontSize: 11, fill: "#94a3b8" }}
        />
        <Tooltip
          formatter={(v) => [`${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(2)}%`, "Alpha vs. Peers"]}
          contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
          labelStyle={{ color: "#e2e8f0" }}
        />
        <ReferenceLine y={0} stroke="#475569" />
        <Bar dataKey="alpha" radius={[4, 4, 0, 0]}>
          {data.map((entry, index) => (
            <Cell
              key={index}
              fill={(entry.alpha ?? 0) >= 0 ? "#22c55e" : "#ef4444"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
