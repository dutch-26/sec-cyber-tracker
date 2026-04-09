// Server-only module — only import from server components or server actions
import path from "path";
import fs from "fs";
import type { Incident, Meta } from "./types";

export type { Incident, Meta };
export { formatPct, formatCap, computeStats } from "./types";

function getDataDir(): string {
  // Resolves to /repo-root/data/ regardless of whether cwd is web/ or root
  const cwd = process.cwd();
  // On Vercel, cwd is the project root (monorepo root or web/)
  const candidate1 = path.join(cwd, "data");
  const candidate2 = path.join(cwd, "..", "data");
  return fs.existsSync(candidate1) ? candidate1 : candidate2;
}

export function getAllIncidents(): Incident[] {
  try {
    const filePath = path.join(getDataDir(), "incidents.json");
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw) as Incident[];
  } catch {
    return [];
  }
}

export function getMeta(): Meta {
  try {
    const filePath = path.join(getDataDir(), "meta.json");
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw) as Meta;
  } catch {
    return { last_updated: null, total_incidents: 0 };
  }
}

export function getIncidentById(id: string): Incident | undefined {
  return getAllIncidents().find((i) => i.id === id);
}
