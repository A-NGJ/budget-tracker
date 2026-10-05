// Display formatting for exact decimal strings. Amounts are never converted to
// numbers, so what is shown is exactly what the bank exported.

const MINUS = "\u2212";

/** "-7800.00" → "−7,800.00" */
export function formatDecimal(amount: string): string {
  const negative = amount.startsWith("-");
  const [integer, fraction] = (negative ? amount.slice(1) : amount).split(".");
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? MINUS : ""}${grouped}${fraction ? `.${fraction}` : ""}`;
}

export function formatMoney(amount: string, currency: string): string {
  return `${formatDecimal(amount)} ${currency}`;
}

/** "2026-09-05" → "5 Sep 2026", without time zones getting involved. */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const name = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][month - 1];
  return `${day} ${name} ${year}`;
}

export function formatPeriod(period: { from: string; to: string }): string {
  return period.from === period.to ? formatDate(period.from) : `${formatDate(period.from)} – ${formatDate(period.to)}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
