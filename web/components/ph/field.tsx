"use client";
// The position hub's field: the DEFENSE's half, drawn the way a defensive staff draws it — offense at the bottom,
// the line of scrimmage in yellow, depth going up the page. Coordinates are the standardized frame from the Python
// side: depth = yards off the ball, lateral = yards from the ball with + = the defense's right. Seen from behind the
// offense the defense's right is on the LEFT of the page, so the corners are labelled rather than left to memory.
import { useMemo, useState } from "react";
import type { Heat, Snap } from "@/lib/ph";
import { ROLE_COLOR, ROLE_LABEL, downDistance } from "@/lib/roles";
import { cn } from "@/lib/utils";

export const W = 640, H = 440;
const X0 = -27, X1 = 27, Y0 = -3, Y1 = 22;
export const sx = (lat: number) => ((-lat - X0) / (X1 - X0)) * W;          // defense's right on the page's left
export const sy = (depth: number) => H - ((depth - Y0) / (Y1 - Y0)) * H;

export function FieldBase({ children, className, caption }: { children?: React.ReactNode; className?: string; caption?: string }) {
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={cn("w-full rounded-xl border border-ink-700 bg-[#0d1a12]", className)} role="img" aria-label={caption}>
      {[0, 5, 10, 15, 20].map((d) => (
        <g key={d}>
          <line x1={0} x2={W} y1={sy(d)} y2={sy(d)} stroke={d === 0 ? "#f1c40f" : "rgba(255,255,255,0.10)"} strokeWidth={d === 0 ? 2 : 1} />
          {d > 0 && <text x={8} y={sy(d) - 4} className="fill-white/35 text-[11px] font-semibold">{d} yd</text>}
        </g>
      ))}
      {[-20, -10, 0, 10, 20].map((l) => <line key={l} x1={sx(l)} x2={sx(l)} y1={sy(-3)} y2={sy(22)} stroke="rgba(255,255,255,0.05)" />)}
      <rect x={sx(0) - 4} y={sy(0) - 3} width={8} height={6} rx={2} fill="#8B5A2B" />
      <text x={W / 2} y={H - 8} textAnchor="middle" className="fill-white/40 text-[11px] font-bold uppercase tracking-[0.14em]">Offense</text>
      <text x={10} y={16} className="fill-white/45 text-[11px] font-bold uppercase tracking-[0.12em]">Defense&apos;s right</text>
      <text x={W - 10} y={16} textAnchor="end" className="fill-white/45 text-[11px] font-bold uppercase tracking-[0.12em]">Defense&apos;s left</text>
      {children}
    </svg>
  );
}

/** Every snap, where he stood, colored by the job the charter would call it. Faded dots are the snaps where the
 *  model was unsure (the soft ones). Click a dot for its film. */
export function AlignmentMap({ snaps, selected, onPick, active }: { snaps: Snap[]; selected: Snap | null; onPick: (s: Snap) => void; active: Set<string> }) {
  const [hover, setHover] = useState<Snap | null>(null);
  const shown = useMemo(() => snaps.filter((s) => active.has(s.role) && s.depth >= Y0 && s.depth <= Y1 && Math.abs(s.lateral) <= X1), [snaps, active]);
  const tip = hover ?? selected;
  return (
    <div className="relative">
      <FieldBase caption="Alignment at the snap, every snap">
        {shown.map((s) => (
          <circle key={`${s.game_key}-${s.play_id}`} cx={sx(s.lateral)} cy={sy(s.depth)} r={4}
            fill={ROLE_COLOR[s.role] ?? "#8a949c"} fillOpacity={0.25 + 0.6 * Math.max(0, (s.p - 0.4) / 0.6)}
            className="cursor-pointer" onMouseEnter={() => setHover(s)} onMouseLeave={() => setHover(null)} onClick={() => onPick(s)} />
        ))}
        {selected && <circle cx={sx(selected.lateral)} cy={sy(selected.depth)} r={8} fill="none" stroke="#fff" strokeWidth={2} />}
      </FieldBase>
      {tip && (
        <div className="pointer-events-none absolute right-3 top-7 rounded-lg border border-ink-700 bg-ink-800/95 px-3 py-2 text-xs shadow-lg">
          <div className="font-bold text-white">Week {tip.week} · vs {tip.opp ?? "—"} · {downDistance(tip.down, tip.distance)}</div>
          <div className="tnum mt-0.5 text-muted">{tip.depth.toFixed(1)} yd deep · {ROLE_LABEL[tip.role]} ({Math.round(tip.p * 100)}%) · {tip.pa ? "play action" : tip.pass ? "pass" : "run"}</div>
        </div>
      )}
    </div>
  );
}

function density(snaps: Snap[], heat: Heat) {
  const [by, bx] = heat.bins, [y0, y1] = heat.y, [x0, x1] = heat.x;
  const g = Array.from({ length: by }, () => new Array<number>(bx).fill(0));
  let n = 0;
  for (const s of snaps) {
    const i = Math.floor(((s.depth - y0) / (y1 - y0)) * by), j = Math.floor(((s.lateral - x0) / (x1 - x0)) * bx);
    if (i >= 0 && i < by && j >= 0 && j < bx) { g[i][j] += 1; n += 1; }
  }
  return g.map((row) => row.map((v) => v / Math.max(n, 1)));
}

function Grid({ grid, heat, max, title }: { grid: number[][]; heat: Heat; max: number; title: string }) {
  const [by, bx] = heat.bins, [y0, y1] = heat.y, [x0, x1] = heat.x;
  const dy = (y1 - y0) / by, dx = (x1 - x0) / bx;
  return (
    <div>
      <div className="mb-1.5 text-[11px] font-bold uppercase tracking-wider text-muted">{title}</div>
      <FieldBase caption={title}>
        {grid.map((row, i) => row.map((v, j) => v > 0 ? (
          <rect key={`${i}-${j}`} x={Math.min(sx(x0 + j * dx), sx(x0 + (j + 1) * dx))} y={sy(y0 + (i + 1) * dy)}
            width={Math.abs(sx(x0 + dx) - sx(x0))} height={Math.abs(sy(y0) - sy(y0 + dy))}
            fill={`rgba(28,163,224,${Math.min(1, Math.sqrt(v / max)).toFixed(3)})`} />
        ) : null))}
      </FieldBase>
    </div>
  );
}

/** Where he lives vs where his position group lives, same scale. */
export function HeatmapView({ snaps, heat, peerKey, peerLabel }: { snaps: Snap[]; heat: Heat; peerKey: string; peerLabel: string }) {
  const mine = useMemo(() => density(snaps, heat), [snaps, heat]);
  const peers = heat.grids[peerKey];
  const max = Math.max(...mine.flat(), ...(peers ? peers.flat() : [0]));
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Grid grid={mine} heat={heat} max={max} title="Him" />
      {peers ? <Grid grid={peers} heat={heat} max={max} title={peerLabel} /> : <div className="text-sm text-muted">No data</div>}
    </div>
  );
}

/** Snap spot → where he was 2 seconds later (the paper's window). */
export function MovementMap({ snaps, active }: { snaps: Snap[]; active: Set<string> }) {
  const shown = snaps.filter((s) => active.has(s.role) && s.depth_2s != null && s.lateral_2s != null);
  return (
    <FieldBase caption="Snap to two seconds">
      {shown.map((s) => (
        <g key={`${s.game_key}-${s.play_id}`} opacity={0.45}>
          <line x1={sx(s.lateral)} y1={sy(s.depth)} x2={sx(s.lateral_2s!)} y2={sy(Math.max(Y0, Math.min(Y1, s.depth_2s!)))}
            stroke={ROLE_COLOR[s.role] ?? "#8a949c"} strokeWidth={1.2} />
          <circle cx={sx(s.lateral_2s!)} cy={sy(Math.max(Y0, Math.min(Y1, s.depth_2s!)))} r={2} fill={ROLE_COLOR[s.role] ?? "#8a949c"} />
        </g>
      ))}
    </FieldBase>
  );
}
