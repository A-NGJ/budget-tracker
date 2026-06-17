import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

interface EChartProps {
  option: EChartsOption;
  testId: string;
  title: string;
}

// Thin wrapper around echarts-for-react. The default canvas renderer produces
// a <canvas> element inside this container, which the E2E asserts on.
export function EChart({ option, testId, title }: EChartProps) {
  return (
    <section data-testid={testId} style={{ marginBottom: "2rem" }}>
      <h2 style={{ fontSize: "1.1rem", margin: "0 0 0.5rem" }}>{title}</h2>
      <ReactECharts option={option} style={{ height: 360 }} notMerge lazyUpdate />
    </section>
  );
}
