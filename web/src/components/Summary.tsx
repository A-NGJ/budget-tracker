import type { Summary as SummaryData } from "../api";

interface SummaryProps {
  summary: SummaryData;
}

interface Stat {
  label: string;
  value: string;
  testId: string;
}

// Renders the headline totals verbatim from the backend (Decimal strings),
// so the displayed text exactly matches the analytics response values.
export function Summary({ summary }: SummaryProps) {
  const stats: Stat[] = [
    { label: "Total Income", value: summary.total_income, testId: "summary-income" },
    { label: "Total Expenses", value: summary.total_expenses, testId: "summary-expenses" },
    { label: "Net", value: summary.net, testId: "summary-net" },
  ];

  return (
    <section
      data-testid="summary"
      style={{ display: "flex", gap: "1rem", flexWrap: "wrap", marginBottom: "2rem" }}
    >
      {stats.map((stat) => (
        <div
          key={stat.testId}
          data-testid={stat.testId}
          style={{
            flex: "1 1 180px",
            padding: "1rem",
            borderRadius: "8px",
            background: "#1f2937",
            color: "#f9fafb",
          }}
        >
          <div style={{ fontSize: "0.8rem", opacity: 0.7 }}>{stat.label}</div>
          <div data-testid={`${stat.testId}-value`} style={{ fontSize: "1.5rem", fontWeight: 700 }}>
            {stat.value}
          </div>
        </div>
      ))}
    </section>
  );
}
