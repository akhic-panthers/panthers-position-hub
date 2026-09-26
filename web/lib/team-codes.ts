/** Map internal PFF team codes to standard NFL codes for logos and display. */
const PFF_TO_NFL: Record<string, string> = {
  ARZ: "ARI",
  BLT: "BAL",
  CLV: "CLE",
  HST: "HOU",
  LA: "LAR",
  // Washington Commanders: canonical code is WAS (matches ESPN_SLUG/TEAM_COLORS);
  // ESPN slug "wsh" is the current Commanders logo. Normalize any stray WSH -> WAS.
  WSH: "WAS",
};

export function normalizeTeamCode(code: string | null | undefined): string | null {
  if (!code) return null;
  const u = code.trim().toUpperCase();
  return PFF_TO_NFL[u] ?? u;
}

/** The reverse direction: standard NFL codes → the PFF codes the data artifacts key on
    (leslie card, scheme story, self-scout, neighbourhood, team blocks — all PFF-keyed).
    A team-office/team-defense URL can arrive with either form; data lookups need PFF. */
const NFL_TO_PFF: Record<string, string> = {
  ARI: "ARZ", BAL: "BLT", CLE: "CLV", HOU: "HST", LAR: "LA", WSH: "WAS", JAC: "JAX",
};
export function toPffCode(code: string | null | undefined): string {
  if (!code) return "";
  const u = code.trim().toUpperCase();
  return NFL_TO_PFF[u] ?? u;
}
