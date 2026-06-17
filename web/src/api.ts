// Types mirroring the FastAPI `/api/analytics` (AnalyticsSchema) response.
// Decimal fields are serialized as strings by the backend (e.g. "5000.00").

export interface AnalyticsPeriod {
  from_date: string | null;
  to_date: string | null;
  label: string;
}

export interface SubcategoryRow {
  subcategory: string;
  total: string;
  transaction_count: number;
}

export interface CategoryRow {
  category: string;
  total: string;
  percentage: number;
  transaction_count: number;
  subcategories: SubcategoryRow[];
}

export interface MonthRow {
  year: number;
  month: number;
  label: string;
  income: string;
  expenses: string;
  net: string;
  transaction_count: number;
}

export interface SourceRow {
  source: string;
  total_income: string;
  total_expenses: string;
  transaction_count: number;
}

export interface Summary {
  total_transactions: number;
  total_income: string;
  total_expenses: string;
  net: string;
  avg_transaction: string;
  period: AnalyticsPeriod;
}

export interface Analytics {
  summary: Summary;
  category_data: CategoryRow[];
  monthly_data: MonthRow[];
  source_data: SourceRow[];
  period: AnalyticsPeriod;
}

export async function fetchAnalytics(): Promise<Analytics> {
  const response = await fetch("/api/analytics");
  if (!response.ok) {
    throw new Error(`Failed to load analytics: HTTP ${response.status}`);
  }
  return (await response.json()) as Analytics;
}
