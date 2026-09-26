import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ---- formatters --------------------------------------------------------------
// API rates/percentages are ALREADY in percent units (e.g. 11.6 == 11.6%).

export function fmtPct(x: number | null | undefined, digits = 1): string {
  if (x == null || Number.isNaN(x)) return "—";
  return `${x.toFixed(digits)}%`;
}

const MIN_PLAYER_EPA_ABS = 2;

/** Player share of impact EPA (0–100); player% + scheme% = 100 when computable. */
export function epaPlayerSharePct(
  player: number | null | undefined,
  scheme: number | null | undefined,
  minAbsTotal = MIN_PLAYER_EPA_ABS,
): number | null {
  const p = player ?? 0;
  const s = scheme ?? 0;
  const t = p + s;
  const absT = Math.abs(t);
  if (!Number.isFinite(t) || absT < minAbsTotal) return null;
  if (Math.abs(p) + Math.abs(s) > Math.max(1.25 * absT, absT + 1e-9)) return null;
  const pct = (p / t) * 100;
  return Math.min(100, Math.max(0, pct));
}

export function epaSchemeSharePct(
  player: number | null | undefined,
  scheme: number | null | undefined,
  minAbsTotal = MIN_PLAYER_EPA_ABS,
): number | null {
  const playerShare = epaPlayerSharePct(player, scheme, minAbsTotal);
  if (playerShare == null) return null;
  return Math.min(100, Math.max(0, 100 - playerShare));
}

/** Model attribution % from API (0–100%, magnitude-weighted share). */
export function fmtModelAttributionPct(x: number | null | undefined, digits = 1): string {
  if (x == null || Number.isNaN(x)) return "—";
  return `${x.toFixed(digits)}%`;
}

export function fmtEpa(x: number | null | undefined, signed = false): string {
  if (x == null || Number.isNaN(x)) return "—";
  const s = x.toFixed(2);
  return signed && x > 0 ? `+${s}` : s;
}

export function fmtEpa3(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return "—";
  return x.toFixed(3);
}

export function fmtNum(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return "—";
  return x.toLocaleString("en-US");
}

export function fmtSigned(x: number | null | undefined, digits = 2): string {
  if (x == null || Number.isNaN(x)) return "—";
  const s = x.toFixed(digits);
  return x > 0 ? `+${s}` : s;
}

// Color for a signed value (positive = good-blue, negative = muted-red).
export function signColor(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return "var(--muted)";
  return x >= 0 ? "#1CA3E0" : "#EF6A5E";
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
