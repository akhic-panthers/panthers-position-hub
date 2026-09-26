"use client";
// The Player Room for a receiver, tight end or back. Same furniture as the defensive room: role mix from the gated
// offensive model, then the descriptive layer — routes, usage, who covered him, whom he blocked — and film.
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { StatCard } from "@/components/ui/stat-card";
import { OffAlignmentMap, OffHeatmap, RouteMap } from "@/components/ph/field-offense";
import { RoleLegend, ShareRow } from "@/components/ph/role-bars";
import { FilmPanel } from "@/components/ph/film-panel";
import { loadHeatOff, loadOSnaps, pctOf, type Heat, type Index, type OSnap, type PlayerSeason } from "@/lib/ph";
import { GROUP_LABEL, OFF_GROUP_ROLES, OFF_ROLES, OFF_ROLE_COLOR, OFF_ROLE_LABEL, ROLE_LABEL, downDistance, ordinal } from "@/lib/roles";
import { cn } from "@/lib/utils";

const VIEWS = [{ key: "map", label: "Alignment Map" }, { key: "routes", label: "Routes" }, { key: "heat", label: "Heatmap" },
  { key: "covered", label: "Who Covers Him" }, { key: "blocking", label: "Blocking" }];
const FILTERS = [{ key: "all", label: "All snaps" }, { key: "pass", label: "Pass" }, { key: "pa", label: "Play action" }, { key: "run", label: "Run" },
  { key: "tgt", label: "Targets" }, { key: "3rd", label: "3rd down" }];

function Bars({ title, data, color = "#1CA3E0", max = 10, labels }: { title: string; data: Record<string, number> | undefined; color?: string; max?: number; labels?: Record<string, string> }) {
  const rows = Object.entries(data ?? {}).sort((a, b) => b[1] - a[1]).slice(0, max);
  const sum = Object.values(data ?? {}).reduce((a, b) => a + b, 0);
  return (
    <div>
      <div className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted">{title}</div>
      {!rows.length ? <div className="text-sm text-muted">No data</div> : rows.map(([k, v]) => (
        <div key={k} className="grid grid-cols-[170px_1fr_52px] items-center gap-2 py-[3px]">
          <span className="truncate text-[13px] text-foreground">{labels?.[k] ?? k}</span>
          <div className="h-3 overflow-hidden rounded-r-[4px] bg-ink-900"><div className="h-full rounded-r-[4px]" style={{ width: `${(v / sum) * 100}%`, backgroundColor: color }} /></div>
          <span className="tnum text-right text-[12px] font-semibold text-white">{Math.round((v / sum) * 100)}%</span>
        </div>
      ))}
    </div>
  );
}

export function OffenseRoom({ player, idx }: { player: PlayerSeason; idx: Index }) {
  const q = useSearchParams();
  const router = useRouter();
  const [snaps, setSnaps] = useState<OSnap[] | null>(null);
  const [heat, setHeat] = useState<Heat | null>(null);
  const [picked, setPicked] = useState<OSnap | null>(null);
  const [filter, setFilter] = useState("all");
  const [route, setRoute] = useState<string | null>(null);
  const [active, setActive] = useState<Set<string>>(new Set(OFF_ROLES));
  const view = q.get("view") && VIEWS.some((v) => v.key === q.get("view")) ? q.get("view")! : "map";
  const setView = (v: string) => { const n = new URLSearchParams(q.toString()); n.set("view", v); router.replace(`/player?${n}`, { scroll: false }); };

  useEffect(() => {
    setSnaps(null); setPicked(null); setRoute(null);
    loadOSnaps(player.id, player.season, idx.meta.off_roles).then(setSnaps).catch(() => setSnaps([]));
    loadHeatOff().then(setHeat).catch(() => {});
  }, [player, idx]);

  const filtered = useMemo(() => (snaps ?? []).filter((s) => filter === "all" ? true : filter === "pass" ? s.pass : filter === "pa" ? s.pa
    : filter === "run" ? !s.pass : filter === "tgt" ? s.targeted : filter === "3rd" ? s.down === 3 : true), [snaps, filter]);
  const order = [...(OFF_GROUP_ROLES[player.group] ?? OFF_ROLES)].filter((r) => (player.align[r] ?? 0) >= 0.005);
  const u = player.usage!;
  const topRoutes = Object.entries(player.routes ?? {}).filter(([k]) => k !== "Stayed in to block").sort((a, b) => b[1] - a[1]).slice(0, 8);

  return (
    <>
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatCard label="Snaps" metricKey="snaps" value={player.snaps.toLocaleString("en-US")} />
        <StatCard label="Primary Job" value={<span className="text-[18px]">{OFF_ROLE_LABEL[player.primary]}</span>} accent={OFF_ROLE_COLOR[player.primary]} />
        <StatCard label="Jobs" metricKey="jobs" value={player.entropy.toFixed(2)} sub={player.pct.align_entropy != null ? `${ordinal(player.pct.align_entropy)} percentile` : undefined} />
        <StatCard label="Targets Per Route" value={pctOf(u.target_rate)} sub={`${u.targets} targets on ${u.routes} routes${player.pct.target_rate != null ? ` · ${ordinal(player.pct.target_rate)} pct` : ""}`} />
        <StatCard label="Motion Or Shift" value={pctOf(u.motion_rate)} sub={`${pctOf(u.motion_at_snap_rate)} moving at the snap`} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_440px]">
        <div className="space-y-5">
          <div className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900 p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <div className="flex flex-wrap gap-1 rounded-lg border border-ink-700 bg-ink-900/40 p-0.5">
                {VIEWS.map((v) => (
                  <button key={v.key} type="button" onClick={() => setView(v.key)}
                    className={cn("rounded-md px-3 py-1.5 text-[13px] font-semibold transition-colors", v.key === view ? "bg-panthers-blue/20 text-panthers-bright" : "text-muted hover:text-white")}>{v.label}</button>
                ))}
              </div>
              {["map", "routes", "heat"].includes(view) && (
                <div className="ml-auto flex flex-wrap gap-1">
                  {FILTERS.map((f) => (
                    <button key={f.key} type="button" onClick={() => setFilter(f.key)}
                      className={cn("rounded-md px-2.5 py-1 text-[12px] font-semibold", f.key === filter ? "bg-white/[0.08] text-white" : "text-muted hover:text-white")}>{f.label}</button>
                  ))}
                </div>
              )}
            </div>
            {["map", "routes"].includes(view) && (
              <div className="mb-3"><RoleLegend roles={order} active={active} onToggle={(r) => { const n = new Set(active); n.has(r) ? n.delete(r) : n.add(r); setActive(n); }} /></div>
            )}
            {view === "routes" && topRoutes.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-1">
                <button type="button" onClick={() => setRoute(null)} className={cn("rounded-md px-2.5 py-1 text-[12px] font-semibold", !route ? "bg-white/[0.08] text-white" : "text-muted hover:text-white")}>Every route</button>
                {topRoutes.map(([r]) => (
                  <button key={r} type="button" onClick={() => setRoute(r === route ? null : r)}
                    className={cn("rounded-md px-2.5 py-1 text-[12px] font-semibold", r === route ? "bg-white/[0.08] text-white" : "text-muted hover:text-white")}>{r}</button>
                ))}
              </div>
            )}
            {!snaps ? <div className="aspect-[4/3] w-full animate-pulse rounded-xl bg-ink-800" /> : view === "map" ? (
              <OffAlignmentMap snaps={filtered} active={active} selected={picked} onPick={setPicked} />
            ) : view === "routes" ? (
              <RouteMap snaps={filtered} active={active} selected={picked} onPick={setPicked} route={route} />
            ) : view === "heat" ? (
              heat ? <OffHeatmap snaps={filtered} heat={heat} peerKey={`${player.group}_${player.season}`} peerLabel={`${GROUP_LABEL[player.group]}, ${player.season}`} /> : <div className="text-sm text-muted">No data</div>
            ) : view === "covered" ? (
              <div className="grid gap-6 md:grid-cols-2">
                <Bars title="The defender PFF charted on him" data={player.covered?.by_role} labels={ROLE_LABEL} color="#F43F5E" />
                <Bars title="The coverage he saw" data={player.covered?.by_call} color="#A78BFA" />
                <Bars title="Who covered him most" data={player.covered?.by_player} color="#8A949C" max={8} />
              </div>
            ) : (
              <div className="grid gap-6 md:grid-cols-2">
                <Bars title="How he blocked" data={player.blocking?.types} color="#F59E0B" />
                <Bars title="Who he blocked" data={player.blocking?.blocked_roles} labels={ROLE_LABEL} color="#F43F5E" />
              </div>
            )}
            <p className="mt-2 text-[12px] text-muted">
              {view === "map" && `${filtered.length.toLocaleString("en-US")} snaps. Each dot is where he stood at the snap; faded dots are snaps a charter could call more than one way. Click one for its film.`}
              {view === "routes" && "Each line is his first three seconds after the snap; targets are drawn brighter. Route names are PFF's charting. Click a route for its film."}
              {view === "heat" && "Where he lined up, against every player at his position this season, on the same scale."}
              {view === "covered" && "From PFF's coverage charting: the defender assigned to him, read by the job that defender lined up in on that snap."}
              {view === "blocking" && "From PFF's blocking chart: every block he made, and the job of the man he blocked."}
            </p>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <div className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900 p-4">
              <div className="mb-2 text-[0.78rem] font-bold uppercase tracking-wide text-panthers-bright">Where He Lines Up</div>
              {order.map((r) => <ShareRow key={r} label={OFF_ROLE_LABEL[r]} value={player.align[r]} pct={player.pct[`share_${r}`]} color={OFF_ROLE_COLOR[r]} />)}
              <p className="mt-2 text-[12px] text-muted">
                Wide receivers: {pctOf(u.x_share_of_wide)} on the line (an X), the rest off it (a Z). Tight end snaps: {pctOf(u.wing_share_of_te)} off the line as a wing. Both from PFF&apos;s charting.
              </p>
            </div>
            <div className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900 p-4">
              <div className="mb-2 text-[0.78rem] font-bold uppercase tracking-wide text-panthers-bright">What He Does On The Snap</div>
              <Bars title="PFF's charted job" data={player.roles_charted} color="#10B981" />
              <div className="mt-4"><Bars title="Route tree" data={player.routes} color="#1CA3E0" max={8} /></div>
              {u.mean_route_depth != null && <p className="mt-2 text-[12px] text-muted">Average depth of the break: {u.mean_route_depth.toFixed(1)} yards.</p>}
            </div>
          </div>

          <div className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900 p-4">
            <Bars title="Motion and shifts (PFF's charting)" data={player.motions} color="#A78BFA" />
            <p className="mt-3 text-[12px] text-muted">An offensive player&apos;s role mix repeats season to season, but about half of that repeat comes from how his offense deploys its personnel, not from him. Read his mix beside his team&apos;s formations.</p>
          </div>
        </div>

        <div className="space-y-5">
          <FilmPanel snap={picked ? { ...picked, context: `${OFF_ROLE_LABEL[picked.role]}${picked.route ? ` · ${picked.route}` : ""}${picked.targeted ? " · targeted" : ""}${picked.carrier ? " · the carry" : ""}` } : null} playerName={player.name} />
          {snaps && <TargetList snaps={snaps} picked={picked} onPick={setPicked} />}
        </div>
      </div>
    </>
  );
}

function TargetList({ snaps, picked, onPick }: { snaps: OSnap[]; picked: OSnap | null; onPick: (s: OSnap) => void }) {
  const tg = [...snaps].filter((s) => s.targeted || s.carrier).reverse().slice(0, 16);
  return (
    <div className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900 p-4">
      <div className="mb-2 text-[0.78rem] font-bold uppercase tracking-wide text-panthers-bright">Film · Targets And Carries</div>
      {!tg.length ? <div className="text-sm text-muted">No data</div> : (
        <div className="flex flex-wrap gap-1">
          {tg.map((s) => (
            <button key={`${s.game_key}-${s.play_id}`} type="button" onClick={() => onPick(s)}
              className={cn("rounded-md border px-2 py-1 text-[12px] transition-colors", picked?.play_id === s.play_id && picked?.game_key === s.game_key ? "border-panthers-bright bg-panthers-blue/20 text-white" : "border-ink-700 text-foreground hover:bg-ink-800")}>
              Week {s.week} {s.opp ?? ""} · {downDistance(s.down, s.distance)}{s.route ? ` · ${s.route}` : s.carrier ? " · carry" : ""}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
