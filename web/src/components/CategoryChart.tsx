import type { EChartsOption } from "echarts";
import type { CategoryRow } from "../api";
import { EChart } from "./EChart";

interface CategoryChartProps {
  data: CategoryRow[];
}

// Category breakdown as a pie of expense magnitude per category.
export function CategoryChart({ data }: CategoryChartProps) {
  const option: EChartsOption = {
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { bottom: 0 },
    series: [
      {
        name: "Category",
        type: "pie",
        radius: ["40%", "70%"],
        data: data.map((row) => ({
          name: row.category,
          value: Math.abs(Number(row.total)),
        })),
      },
    ],
  };

  return <EChart option={option} testId="chart-category" title="Category Breakdown" />;
}
