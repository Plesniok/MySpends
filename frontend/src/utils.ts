import type { ReceiptStatus } from "./types";

export function formatMoney(grosze: number | null, currency = "PLN"): string {
  if (grosze == null) return "—";
  return new Intl.NumberFormat("pl-PL", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(grosze / 100);
}

export function formatDate(value: string | null, options?: Intl.DateTimeFormatOptions): string {
  if (!value) return "Brak daty";
  return new Intl.DateTimeFormat("pl-PL", options || { day: "numeric", month: "short", year: "numeric" }).format(
    new Date(value),
  );
}

export function formatQuantity(value: string, unit: string): string {
  const amount = Number(value);
  const formatted = Number.isFinite(amount)
    ? new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 3 }).format(amount)
    : value;
  return `${formatted} ${unit}`;
}

export const statusLabels: Record<ReceiptStatus, { label: string; tone: string }> = {
  uploaded: { label: "Wysłany", tone: "neutral" },
  processing: { label: "Analizowanie", tone: "info" },
  needs_review: { label: "Do sprawdzenia", tone: "warning" },
  completed: { label: "Gotowy", tone: "success" },
  failed: { label: "Błąd", tone: "danger" },
};

const categoryTones = ["mint", "amber", "violet", "blue", "rose", "teal", "orange"];

export function categoryTone(name: string): string {
  let hash = 0;
  for (const character of name) hash = (hash * 31 + character.charCodeAt(0)) | 0;
  return categoryTones[Math.abs(hash) % categoryTones.length];
}
