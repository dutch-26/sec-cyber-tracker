import { Badge } from "@/components/ui/badge";

interface Props {
  predicted: boolean | null;
  confidence?: number | null;
}

export default function RiskBadge({ predicted, confidence }: Props) {
  if (predicted === null || predicted === undefined) {
    return <Badge variant="secondary">No Analysis</Badge>;
  }

  if (predicted) {
    const highConf = confidence !== null && confidence !== undefined && confidence >= 0.7;
    return (
      <Badge className="bg-emerald-600 hover:bg-emerald-700 text-white">
        {highConf ? "Predicted (High Confidence)" : "Predicted"}
      </Badge>
    );
  }

  return (
    <Badge className="bg-red-700 hover:bg-red-800 text-white">
      Not Predicted
    </Badge>
  );
}
