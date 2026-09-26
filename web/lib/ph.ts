// Static stores written by `poshub export-web` into public/ph/ (gitignored, per-snap rows stay on this machine).
// Module-level cache with a shared in-flight promise, the pattern the sister app uses for /public stores.
export type Blocks = {
  charted_snaps: number; blocked_snaps: number | null; unblocked_rate: number | null; looper_rate: number | null; double_team_rate: number | null;
  blockers: Record<string, number>; types: Record<string, number>; gaps: Record<string, number>; jobs: Record<string, number>; moves: Record<string, number>;
};
export type CallSplit = { deep_share_one_high: number | null; deep_share_two_high: number | null; middle_share_one_high: number | null;
  box_share_one_high: number | null; call_explains: number | null };
export type Usage = { routes: number; targets: number; carries: number; target_rate: number | null; mean_route_depth: number | null;
  motion_rate: number | null; motion_at_snap_rate: number | null; x_share_of_wide: number | null; wing_share_of_te: number | null };
export type PlayerSeason = {
  side: "D" | "O"; id: number; name: string; team: string; season: number; pos: string; group: string; snaps: number; primary: string;
  entropy: number; depth?: number; box?: number; head: string | null;
  align: Record<string, number | null>; resp?: Record<string, number | null>; pct: Record<string, number>;
  call?: CallSplit | null; blocks?: Blocks | null;
  // offense
  usage?: Usage; roles_charted?: Record<string, number>; routes?: Record<string, number>; motions?: Record<string, number>;
  covered?: { by_role: Record<string, number>; by_call: Record<string, number>; by_player: Record<string, number> };
  blocking?: { types: Record<string, number>; blocked_roles: Record<string, number> };
};
export type Index = { meta: { roles: string[]; resp: string[]; off_roles: string[] }; players: PlayerSeason[] };
export type Snap = { game_key: number; play_id: number; week: number; depth: number; lateral: number; depth_2s: number | null; lateral_2s: number | null;
  role: string; p: number; resp: string | null; down: number | null; distance: string | null; pass: boolean; pa: boolean; opp: string | null; shell: string | null };
export type Heat = { y: [number, number]; x: [number, number]; bins: [number, number]; grids: Record<string, number[][]> };

const cache = new Map<string, Promise<unknown>>();
function load<T>(path: string): Promise<T> {
  let p = cache.get(path) as Promise<T> | undefined;
  if (!p) {
    p = fetch(path).then((r) => { if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`); return r.json() as Promise<T>; });
    cache.set(path, p);
    p.catch(() => cache.delete(path));
  }
  return p;
}
export const loadIndex = () => load<Index>("/ph/index.json");
export const loadHeat = () => load<Heat>("/ph/heat.json");
export const loadHeatOff = () => load<Heat>("/ph/heat_off.json");
export const loadTeams = () => load<Record<string, unknown>[]>("/ph/teams.json");
export const loadGates = () => load<Record<string, Record<string, unknown>[]>>("/ph/gates.json");
export async function loadSnaps(id: number, season: number, roles: string[], resp: string[]): Promise<Snap[]> {
  const d = await load<{ cols: string[]; snaps: (number | string | null)[][] }>(`/ph/p/${id}_${season}.json`);
  return d.snaps.map((r) => ({
    game_key: r[0] as number, play_id: r[1] as number, week: r[2] as number, depth: r[3] as number, lateral: r[4] as number,
    depth_2s: r[5] as number | null, lateral_2s: r[6] as number | null, role: roles[r[7] as number] ?? "?", p: r[8] as number,
    resp: (r[9] as number) >= 0 ? resp[r[9] as number] : null, down: r[10] as number | null, distance: r[11] as string | null,
    pass: r[12] === 1, pa: r[13] === 1, opp: r[14] as string | null, shell: r[15] as string | null,
  }));
}
export function pctOf(x: number | null | undefined, digits = 0): string {
  return x == null || Number.isNaN(x) ? "—" : `${(x * 100).toFixed(digits)}%`;
}

/** One offensive snap: where he stood (x = yards past the line, negative = backfield; y + = the offense's left) and his
 *  path every half second for three seconds. */
export type OSnap = { game_key: number; play_id: number; week: number; x: number; y: number; path: [number | null, number | null][];
  role: string; p: number; route: string | null; targeted: boolean; carrier: boolean; job: string | null; down: number | null;
  distance: string | null; pass: boolean; pa: boolean; opp: string | null; covered_by: string | null; on_line: boolean };
export async function loadOSnaps(id: number, season: number, roles: string[]): Promise<OSnap[]> {
  const d = await load<{ snaps: unknown[][] }>(`/ph/p/o${id}_${season}.json`);
  return d.snaps.map((r) => ({
    game_key: r[0] as number, play_id: r[1] as number, week: r[2] as number, x: r[3] as number, y: r[4] as number,
    path: r[5] as [number | null, number | null][], role: roles[r[6] as number] ?? "?", p: r[7] as number, route: r[8] as string | null,
    targeted: r[9] === 1, carrier: r[10] === 1, job: r[11] as string | null, down: r[12] as number | null, distance: r[13] as string | null,
    pass: r[14] === 1, pa: r[15] === 1, opp: r[16] as string | null, covered_by: r[17] as string | null, on_line: r[18] === 1,
  }));
}
