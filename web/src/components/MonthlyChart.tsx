import type { EChartsOption } from "echarts";
import type { MonthRow } from "../api";
import { EChart } from "./EChart";

interface MonthlyChartProps {
  data: MonthRow[];
}

// Monthly income vs. expenses as grouped bars. Expenses are plotted as
// magnitude so both series are positive and visually comparable.
export function MonthlyChart({ data }: MonthlyChartProps) {
  const option: EChartsOption = {
    tooltip: { trigger: "axis" },
    legend: { data: ["Income", "Expenses"], bottom: 0 },
    xAxis: { type: "category", data: data.map((row) => row.label) },
    yAxis: { type: "value" },
    series: [
      {
        name: "Income",
        type: "bar",
        data: data.map((row) => Number(row.income)),
      },
      {
        name: "Expenses",
        type: "bar",
        data: data.map((row) => Math.abs(Number(row.expenses))),
      },
    ],
  };

  return <EChart option={option} testId="chart-monthly" title="Monthly Income / Expenses" />;
}
