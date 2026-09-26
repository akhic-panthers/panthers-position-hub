"use client";
// The offense's view: the line of scrimmage near the bottom third, the backfield below it, routes running up the page.
// Seen from behind the quarterback, so the offense's left is the page's left. Coordinates are the standardized frame
// from the Python side: x = yards past the line (negative = backfield), y = yards from the ball, + = the offense's left.
import { useMemo, useState } from "react";
import type { Heat, OSnap } from "@/lib/ph";
import { OFF_ROLE_COLOR, OFF_ROLE_LABEL, downDistance } from "@/lib/roles";
import { cn } from "@/lib/utils";

const W = 640, H = 480;
const X0 = -27, X1 = 27, Y0 = -10, Y1 = 22;
const sx = (y: number) => ((-y - X0) / (X1 - X0)) * W;
const sy = (x: number) => H - ((x - Y0) / (Y1 - Y0)) * H;
const clampX = (x: number) => Math.max(Y0, Math.min(Y1, x));

function OffenseField({ children, caption }: { children?: React.ReactNode; caption: string }) {
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded-xl border border-ink-700 bg-[#0d1a12]" role="img" aria-label={caption}>
      {[-5, 0, 5, 10, 15, 20].map((d) => (
        <g key={d}>
          <line x1={0} x2={W} y1={sy(d)} y2={sy(d)} stroke={d === 0 ? "#f1c40f" : "rgba(255,255,255,0.10)"} strokeWidth={d === 0 ? 2 : 1} />
          {d !== 0 && <text x={8} y={sy(d) - 4} className="fill-white/35 text-[11px] font-semibold">{d > 0 ? `+${d}` : d} yd</text>}
        </g>
      ))}
      {[-20, -10, 0, 10, 20].map((l) => <line key={l} x1={sx(l)} x2={sx(l)} y1={sy(Y0)} y2={sy(Y1)} stroke="rgba(255,255,255,0.05)" />)}
      <rect x={sx(0) - 4} y={sy(0) - 3} width={8} height={6} rx={2} fill="#8B5A2B" />
      <text x={W / 2} y={16} textAnchor="middle" className="fill-white/40 text-[11px] font-bold uppercase tracking-[0.14em]">Defense</text>
      <text x={10} y={H - 8} className="fill-white/45 text-[11px] font-bold uppercase tracking-[0.12em]">Offense&apos;s left</text>
      <text x={W - 10} y={H - 8} textAnchor="end" className="fill-white/45 text-[11px] font-bold uppercase tracking-[0.12em]">Offense&apos;s right</text>
      {children}
    </svg>
  );
}

function Tip({ s }: { s: OSnap }) {
  return (
    <div className="pointer-events-none absolute right-3 top-7 rounded-lg border border-ink-700 bg-ink-800/95 px-3 py-2 text-xs shadow-lg">
      <div className="font-bold text-white">Week {s.week} · vs {s.opp ?? "—"} · {downDistance(s.down, s.distance)}</div>
      <div className="mt-0.5 text-muted">{OFF_ROLE_LABEL[s.role]} ({Math.round(s.p * 100)}%) · {s.route ?? (s.pass ? "pass" : "run")}{s.targeted ? " · targeted" : ""}{s.carrier ? " · carry" : ""}</div>
    </div>
  );
}

export function OffAlignmentMap({ snaps, active, selected, onPick }: { snaps: OSnap[]; active: Set<string>; selected: OSnap | null; onPick: (s: OSnap) => void }) {
  const [hover, setHover] = useState<OSnap | null>(null);
  const shown = useMemo(() => snaps.filter((s) => active.has(s.role) && Math.abs(s.y) <= X1), [snaps, active]);
  const tip = hover ?? selected;
  return (
    <div className="relative">
      <OffenseField caption="Alignment at the snap, every snap">
        {shown.map((s) => (
          <circle key={`${s.game_key}-${s.play_id}`} cx={sx(s.y)} cy={sy(clampX(s.x))} r={4} fill={OFF_ROLE_COLOR[s.role] ?? "#8a949c"}
            fillOpacity={0.25 + 0.6 * Math.max(0, (s.p - 0.4) / 0.6)} className="cursor-pointer"
            onMouseEnter={() => setHover(s)} onMouseLeave={() => setHover(null)} onClick={() => onPick(s)} />
        ))}
        {selected && <circle cx={sx(selected.y)} cy={sy(clampX(selected.x))} r={8} fill="none" stroke="#fff" strokeWidth={2} />}
      </OffenseField>
      {tip && <Tip s={tip} />}
    </div>
  );
}

/** Every snap's first three seconds, half a second a step. Targets are drawn brighter; click a path for its film. */
export function RouteMap({ snaps, active, selected, onPick, route }: { snaps: OSnap[]; active: Set<string>; selected: OSnap | null; onPick: (s: OSnap) => void; route: string | null }) {
  const [hover, setHover] = useState<OSnap | null>(null);
  const shown = useMemo(() => snaps.filter((s) => active.has(s.role) && (!route || s.route === route) && s.path.some((p) => p[0] != null)), [snaps, active, route]);
  const d = (s: OSnap) => {
    const pts = [[s.x, s.y], ...s.path.filter((p) => p[0] != null && p[1] != null)] as [number, number][];
    return pts.map(([x, y], i) => `${i ? "L" : "M"}${sx(y).toFixed(1)},${sy(clampX(x)).toFixed(1)}`).join(" ");
  };
  const tip = hover ?? selected;
  return (
    <div className="relative">
      <OffenseField caption="Snap to three seconds">
        {shown.map((s) => {
          const on = selected?.play_id === s.play_id && selected?.game_key === s.game_key;
          return (
            <path key={`${s.game_key}-${s.play_id}`} d={d(s)} fill="none" stroke={on ? "#ffffff" : OFF_ROLE_COLOR[s.role] ?? "#8a949c"}
              strokeOpacity={on ? 1 : s.targeted ? 0.85 : 0.3} strokeWidth={on ? 2.5 : s.targeted ? 1.6 : 1.1} className="cursor-pointer"
              onMouseEnter={() => setHover(s)} onMouseLeave={() => setHover(null)} onClick={() => onPick(s)} />
          );
        })}
      </OffenseField>
      {tip && <Tip s={tip} />}
    </div>
  );
}

function density(snaps: OSnap[], heat: Heat) {
  const [by, bx] = heat.bins, [y0, y1] = heat.y, [x0, x1] = heat.x;
  const g = Array.from({ length: by }, () => new Array<number>(bx).fill(0));
  let n = 0;
  for (const s of snaps) {
    const i = Math.floor(((s.x - y0) / (y1 - y0)) * by), j = Math.floor(((s.y - x0) / (x1 - x0)) * bx);
    if (i >= 0 && i < by && j >= 0 && j < bx) { g[i][j] += 1; n += 1; }
  }
  return g.map((r) => r.map((v) => v / Math.max(n, 1)));
}

function Grid({ grid, heat, max, title }: { grid: number[][]; heat: Heat; max: number; title: string }) {
  const [by, bx] = heat.bins, [y0, y1] = heat.y, [x0, x1] = heat.x;
  const dy = (y1 - y0) / by, dx = (x1 - x0) / bx;
  return (
    <div>
      <div className="mb-1.5 text-[11px] font-bold uppercase tracking-wider text-muted">{title}</div>
      <OffenseField caption={title}>
        {grid.map((row, i) => row.map((v, j) => v > 0 ? (
          <rect key={`${i}-${j}`} x={Math.min(sx(x0 + j * dx), sx(x0 + (j + 1) * dx))} y={sy(y0 + (i + 1) * dy)}
            width={Math.abs(sx(x0 + dx) - sx(x0))} height={Math.abs(sy(y0) - sy(y0 + dy))} fill={`rgba(28,163,224,${Math.min(1, Math.sqrt(v / max)).toFixed(3)})`} />
        ) : null))}
      </OffenseField>
    </div>
  );
}

export function OffHeatmap({ snaps, heat, peerKey, peerLabel, className }: { snaps: OSnap[]; heat: Heat; peerKey: string; peerLabel: string; className?: string }) {
  const mine = useMemo(() => density(snaps, heat), [snaps, heat]);
  const peers = heat.grids[peerKey];
  const max = Math.max(...mine.flat(), ...(peers ? peers.flat() : [0]));
  return (
    <div className={cn("grid gap-4 xl:grid-cols-2", className)}>
      <Grid grid={mine} heat={heat} max={max} title="Him" />
      {peers ? <Grid grid={peers} heat={heat} max={max} title={peerLabel} /> : <div className="text-sm text-muted">No data</div>}
    </div>
  );
}
