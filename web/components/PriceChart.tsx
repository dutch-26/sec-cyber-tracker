"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import type { Incident } from "@/lib/types";

interface Props {
  incident: Incident;
}

export default function PriceChart({ incident }: Props) {
  const { return_t0, return_t30, return_t60, return_t90,
          peer_return_t0, peer_return_t30, peer_return_t60, peer_return_t90 } = incident;

  const data = [
    {
      label: "T-1 (Baseline)",
      company: 0,
      peer: 0,
    },
    {
      label: "T+0 (Filing Day)",
      company: return_t0 !== null ? +(return_t0 * 100).toFixed(2) : null,
      peer: peer_return_t0 !== null ? +(peer_return_t0 * 100).toFixed(2) : null,
    },
    {
      label: "T+30",
      company: return_t30 !== null ? +(return_t30 * 100).toFixed(2) : null,
      peer: peer_return_t30 !== null ? +(peer_return_t30 * 100).toFixed(2) : null,
    },
    {
      label: "T+60",
      company: return_t60 !== null ? +(return_t60 * 100).toFixed(2) : null,
      peer: peer_return_t60 !== null ? +(peer_return_t60 * 100).toFixed(2) : null,
    },
    {
      label: "T+90",
      company: return_t90 !== null ? +(return_t90 * 100).toFixed(2) : null,
      peer: peer_return_t90 !== null ? +(peer_return_t90 * 100).toFixed(2) : null,
    },
  ];

  const fmt = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#94a3b8" }} />
        <YAxis
          tickFormatter={(v) => `${v > 0 ? "+" : ""}${v}%`}
          tick={{ fontSize: 11, fill: "#94a3b8" }}
        />
        <Tooltip
          formatter={(v, name) => [fmt(Number(v)), name === "company" ? incident.ticker : `${incident.peer_etf} (Peers)`]}
          contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
          labelStyle={{ color: "#e2e8f0" }}
        />
        <Legend
          formatter={(v) => (v === "company" ? incident.ticker : `${incident.peer_etf} Sector ETF`)}
          wrapperStyle={{ fontSize: 12 }}
        />
        <ReferenceLine y={0} stroke="#475569" strokeDasharray="4 4" />
        <Line
          type="monotone"
          dataKey="company"
          stroke="#f97316"
          strokeWidth={2}
          dot={{ r: 4, fill: "#f97316" }}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="peer"
          stroke="#60a5fa"
          strokeWidth={2}
          strokeDasharray="5 5"
          dot={{ r: 4, fill: "#60a5fa" }}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
