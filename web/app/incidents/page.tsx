import { getAllIncidents } from "@/lib/data";
import IncidentsClient from "./IncidentsClient";

export const revalidate = 86400;

export default function IncidentsPage() {
  const incidents = getAllIncidents();
  return <IncidentsClient incidents={incidents} />;
}
