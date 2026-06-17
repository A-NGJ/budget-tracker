import type { EChartsOption } from "echarts";
import type { SourceRow } from "../api";
import { EChart } from "./EChart";

interface SourceChartProps {
  data: SourceRow[];
}

// Source breakdown as a pie of expense magnitude per source.
export function SourceChart({ data }: SourceChartProps) {
  const option: EChartsOption = {
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { bottom: 0 },
    series: [
      {
        name: "Source",
        type: "pie",
        radius: "60%",
        data: data.map((row) => ({
          name: row.source,
          value: Math.abs(Number(row.total_expenses)),
        })),
      },
    ],
  };

  return <EChart option={option} testId="chart-source" title="Source Breakdown" />;
}
