// Brand + domain constants shared across the app.

import { normalizeTeamCode } from "@/lib/team-codes";

export const SEASONS = [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018] as const;

export const RUSH_POSITIONS = ["EDGE", "DL", "DT", "LB", "DB"] as const;
export const OL_POSITIONS = ["OT", "OG", "OC", "TE", "RB"] as const;
export const TIERS = ["HIGH", "MIXED", "LOW", "LOW_SIGNAL"] as const;

export const TIER_COLORS: Record<string, string> = {
  HIGH: "#10B981",
  MIXED: "#F59E0B",
  LOW: "#EF4444",
  LOW_SIGNAL: "#8a949c",
};
export const TIER_LABEL: Record<string, string> = {
  HIGH: "High portability",
  MIXED: "Mixed",
  LOW: "Scheme-reliant",
  LOW_SIGNAL: "Insufficient isolated/aided reps",
};

export const DC_TIER_COLORS: Record<string, string> = {
  ELITE_SCHEME_CREATOR: "#0085CA",
  BALANCED_SCHEME: "#5C9BBF",
  TALENT_RELIANT: "#E8A87C",
  INSUFFICIENT_SIGNAL: "#8a949c",
};
export const OC_TIER_COLORS: Record<string, string> = {
  ELITE_SCHEME_PROTECTOR: "#0085CA",
  ELITE_PROTECTION: "#0085CA",
  BALANCED_PROTECTION: "#5C9BBF",
  TALENT_RELIANT: "#E8A87C",
  INSUFFICIENT_SIGNAL: "#8a949c",
};

export const PANTHERS = {
  blue: "#0085CA",
  bright: "#1CA3E0",
  black: "#101820",
  silver: "#BFC0BF",
};

// Section accent (defense / offense / matchup) used for page badges + borders.
export type Section = "defense" | "offense" | "matchup" | "attribution" | "neutral";
export const SECTION_ACCENT: Record<Section, string> = {
  defense: "#DC2626",
  offense: "#0085CA",
  matchup: "#7C3AED",
  attribution: "#10B981",
  neutral: "#8A949C",
};

// Standard NFL code -> ESPN logo slug (API emits standard codes already).
const ESPN_SLUG: Record<string, string> = {
  ARI: "ari", ATL: "atl", BAL: "bal", BUF: "buf", CAR: "car", CHI: "chi",
  CIN: "cin", CLE: "cle", DAL: "dal", DEN: "den", DET: "det", GB: "gb",
  HOU: "hou", IND: "ind", JAX: "jax", KC: "kc", LV: "lv", LAC: "lac",
  LAR: "lar", MIA: "mia", MIN: "min", NE: "ne", NO: "no", NYG: "nyg",
  NYJ: "nyj", PHI: "phi", PIT: "pit", SEA: "sea", SF: "sf", TB: "tb",
  TEN: "ten", WAS: "wsh", OAK: "lv", SD: "lac", STL: "lar",
};

export function teamLogo(code: string | null | undefined): string | null {
  if (!code) return null;
  const nfl = normalizeTeamCode(code);
  if (!nfl) return null;
  const slug = ESPN_SLUG[nfl];
  return slug ? `https://a.espncdn.com/i/teamlogos/nfl/500/${slug}.png` : null;
}

/** Primary jersey colors for field player circles (offense/defense by team code). */
export const TEAM_COLORS: Record<string, string> = {
  ARI: "#97233F",
  ATL: "#A71930",
  BAL: "#241773",
  BUF: "#00338D",
  CAR: "#0085CA",
  CHI: "#0B162A",
  CIN: "#FB4F14",
  CLE: "#311D00",
  DAL: "#003594",
  DEN: "#FB4F14",
  DET: "#0076B6",
  GB: "#203731",
  HOU: "#03202F",
  IND: "#002C5F",
  JAX: "#006778",
  KC: "#E31837",
  LV: "#000000",
  LAC: "#0080C6",
  LAR: "#003594",
  MIA: "#008E97",
  MIN: "#4F2683",
  NE: "#002244",
  NO: "#D3BC8D",
  NYG: "#0B2265",
  NYJ: "#125740",
  PHI: "#004C54",
  PIT: "#FFB612",
  SEA: "#002244",
  SF: "#AA0000",
  TB: "#D50A0A",
  TEN: "#0C2340",
  WAS: "#5A1414",
};

/** Active NFL team codes for filters and sort labels (alphabetical). */
export const NFL_TEAM_CODES = Object.keys(TEAM_COLORS).sort() as (keyof typeof TEAM_COLORS)[];

/** In-game quarters (football), not season weeks. */
export const GAME_QUARTERS = [
  { id: "1", label: "1st quarter" },
  { id: "2", label: "2nd quarter" },
  { id: "3", label: "3rd quarter" },
  { id: "4", label: "4th quarter" },
] as const;

// Pressure-source bucket labels (rush) and protection-source labels.
export const BUCKET_LABEL: Record<string, string> = {
  INVISIBLE_NO_BLOCK_ROW: "Invisible (free runner)",
  A_UNBLOCKED_SCHEME_WIN: "Unblocked by design",
  C_OL_BUST_SCHEME_INDUCED: "OL bust (schemed)",
  B_OL_BUST_NO_SCHEME: "OL bust (vanilla)",
  D_STUNT_WIN: "Stunt win",
  E_BLITZ_OVERLOAD: "Blitz overload",
  F_ZONE_BLITZ_CONFUSION: "Zone-blitz confusion",
  G_SIM_PRESSURE: "Sim pressure",
  H_PLAYER_FAST_WIN: "Player fast win",
  I_PLAYER_NORMAL_WIN: "Player normal win",
  J_COVERAGE_SACK: "Coverage sack",
  VANILLA_NO_PRESSURE: "Vanilla, no pressure",
  Z_UNCLASSIFIED: "Unclassified",
};

export const OUTCOME_LABEL: Record<string, string> = {
  sack: "Sack",
  pressure_int: "Pressure → INT",
  pressure_incomplete: "Pressure → Incomplete",
  hurry_qb_moved: "Hurry (QB moved)",
  pressure_quick_release: "Quick-release pressure",
  pressure_no_impact: "No-impact pressure",
  no_pressure: "No pressure",
  clean_block: "Clean block",
};

export const SCHEME_LABEL: Record<string, string> = {
  vanilla_4man: "Vanilla 4-man",
  blitz: "Blitz",
  stunt: "Stunt",
  mug: "Mug",
  dl_drop: "DL drop",
};

export const SCHEME_CALLS = [
  "vanilla_4man",
  "blitz",
  "stunt",
  "mug",
  "dl_drop",
] as const;

export const ATTACK_LABEL: Record<string, string> = {
  player_isolated: "Player-isolated",
  scheme_aided: "Scheme-aided",
};
