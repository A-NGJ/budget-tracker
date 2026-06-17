import { useEffect, useState } from "react";
import { fetchAnalytics, type Analytics } from "./api";
import { Summary } from "./components/Summary";
import { CategoryChart } from "./components/CategoryChart";
import { MonthlyChart } from "./components/MonthlyChart";
import { SourceChart } from "./components/SourceChart";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: Analytics };

export function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    fetchAnalytics()
      .then((data) => {
        if (active) setState({ status: "ready", data });
      })
      .catch((err: unknown) => {
        if (active) {
          setState({ status: "error", message: err instanceof Error ? err.message : String(err) });
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main
      style={{
        maxWidth: 960,
        margin: "0 auto",
        padding: "2rem 1.5rem",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <h1 style={{ fontSize: "1.6rem", marginBottom: "1.5rem" }}>Budget Tracker — Stats</h1>

      {state.status === "loading" && <p data-testid="loading">Loading analytics…</p>}

      {state.status === "error" && (
        <p data-testid="error" style={{ color: "#b91c1c" }}>
          {state.message}
        </p>
      )}

      {state.status === "ready" && (
        <div data-testid="dashboard">
          <p data-testid="period" style={{ opacity: 0.7, marginTop: 0 }}>
            {state.data.summary.period.label}
          </p>
          <Summary summary={state.data.summary} />
          <CategoryChart data={state.data.category_data} />
          <MonthlyChart data={state.data.monthly_data} />
          <SourceChart data={state.data.source_data} />
        </div>
      )}
    </main>
  );
}
