import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value?: string | null) {
  if (!value) return "Not provided";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

export function formatMoney(
  minimum?: number | null,
  maximum?: number | null,
) {
  if (!minimum && !maximum) return null;
  const compact = (value: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
      notation: value >= 100_000 ? "compact" : "standard",
    }).format(value);
  if (minimum && maximum) return `${compact(minimum)}–${compact(maximum)}`;
  return minimum ? `From ${compact(minimum)}` : `Up to ${compact(maximum!)}`;
}

export function titleCase(value: string) {
  return value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
