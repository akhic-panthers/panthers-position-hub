"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/nav/section-badge";
import { StatCard } from "@/components/ui/stat-card";
import { TeamLogo } from "@/components/ui/team-logo";
import { CardsSkeleton, EmptyState, ErrorState } from "@/components/ui/states";
import { PlayerHeadshot } from "@/components/ph/headshot";
import { ShareRow, RoleLegend } from "@/components/ph/role-bars";
import { AlignmentMap, HeatmapView, MovementMap } from "@/components/ph/field";
import { BlockMap } from "@/components/ph/block-map";
import { FilmPanel } from "@/components/ph/film-panel";
import { loadHeat, loadIndex, loadSnaps, pctOf, type Heat, type Index, type PlayerSeason, type Snap } from "@/lib/ph";
import { GROUP_LABEL, GROUP_ROLES, RESP, RESP_LABEL, ROLES, ROLE_COLOR, ROLE_LABEL, downDistance, ordinal } from "@/lib/roles";
import { cn } from "@/lib/utils";

const VIEWS = [
  { key: "map", label: "Alignment Map" }, { key: "heat", label: "Heatmap" }, { key: "move", label: "First Two Seconds" }, { key: "blocks", label: "Block Map" },
];
const PLAY_FILTERS = [{ key: "all", label: "All snaps" }, { key: "pass", label: "Pass" }, { key: "pa", label: "Play action" }, { key: "run", label: "Run" }, { key: "3rd", label: "3rd down" }];
const RESP_COLOR: Record<string, string> = { RUSH: "#F43F5E", RUN_FIT: "#F59E0B", MAN: "#A78BFA", MAN_MATCH: "#C4B5FD", UNDER_ZONE: "#10B981", DEEP_ZONE: "#22D3EE" };

function PlayerRoom() {
  const q = useSearchParams();
  const router = useRouter();
  const [idx, setIdx] = useState<Index | null>(null);
  const [heat, setHeat] = useState<Heat | null>(null);
  const [snaps, setSnaps] = useState<Snap[] | null>(null);
  const [err, setErr] = useState<Error | null>(null);
  const [picked, setPicked] = useState<Snap | null>(null);
  const [filter, setFilter] = useState("all");
  const [active, setActive] = useState<Set<string>>(new Set(ROLES));

  useEffect(() => { loadIndex().then(setIdx).catch(setErr); loadHeat().then(setHeat).catch(() => {}); }, []);

  // default: the Panthers' most-used safety in the latest season
  const player: PlayerSeason | null = useMemo(() => {
    if (!idx) return null;
    const id = Number(q.get("id")), season = Number(q.get("season"));
    if (id) return idx.players.find((p) => p.id === id && (!season || p.season === season)) ?? null;
    const latest = Math.max(...idx.players.map((p) => p.season));
    return idx.players.filter((p) => p.team === "CAR" && p.group === "S" && p.season === latest).sort((a, b) => b.snaps - a.snaps)[0] ?? null;
  }, [idx, q]);
  const otherSeasons = useMemo(() => (idx && player ? idx.players.filter((p) => p.id === player.id).sort((a, b) => a.season - b.season) : []), [idx, player]);

  useEffect(() => {
    if (!player || !idx) return;
    setSnaps(null); setPicked(null);
    loadSnaps(player.id, player.season, idx.meta.roles, idx.meta.resp).then(setSnaps).catch(setErr);
  }, [player, idx]);

  const view = q.get("view") ?? "map";
  const setView = (v: string) => { const n = new URLSearchParams(q.toString()); n.set("view", v); router.replace(`/player?${n}`, { scroll: false }); };

  const filtered = useMemo(() => (snaps ?? []).filter((s) =>
    filter === "all" ? true : filter === "pass" ? s.pass : filter === "pa" ? s.pa : filter === "run" ? !s.pass : filter === "3rd" ? s.down === 3 : true), [snaps, filter]);

  if (err) return <ErrorState error={err} />;
  if (!idx) return <CardsSkeleton count={4} />;
  if (!player) return <EmptyState title="No player" message="That player-season is not on the board (under 100 snaps)." />;

  const groupRoles = GROUP_ROLES[player.group] ?? [...ROLES];
  const roleOrder = [...groupRoles, ...ROLES.filter((r) => !groupRoles.includes(r))].filter((r) => (player.align[r] ?? 0) >= 0.005);
  const top = roleOrder.filter((r) => (player.align[r] ?? 0) >= 0.05).map((r) => `${Math.round((player.align[r] ?? 0) * 100)}% ${ROLE_LABEL[r].toLowerCase()}`).join(" · ");

  return (
    <>
      <PageHeader section="defense" badge={`Player Room · ${GROUP_LABEL[player.group] ?? player.group}`} title={player.name} subtitle={top} subtitleClassName="max-w-4xl" />

      <div className="mb-5 flex flex-wrap items-center gap-4">
        <PlayerHeadshot name={player.name} url={player.head} size={72} />
        <div className="flex items-center gap-3 text-[14px]">
          <TeamLogo team={player.team} size={26} />
          <span className="text-muted">Listed {player.pos}</span>
        </div>
        <div className="ml-auto flex gap-1 rounded-lg border border-ink-700 bg-ink-900/40 p-0.5">
          {otherSeasons.map((p) => (
            <Link key={p.season} href={`/player?id=${p.id}&season=${p.season}&view=${view}`}
              className={cn("rounded-md px-3 py-1.5 text-[13px] font-semibold transition-colors", p.season === player.season ? "bg-panthers-blue/20 text-panthers-bright" : "text-muted hover:text-white")}>
              {p.season} <span className="text-[11px] opacity-70">{p.team}</span>
            </Link>
          ))}
        </div>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatCard label="Snaps" metricKey="snaps" value={player.snaps.toLocaleString("en-US")} />
        <StatCard label="Primary Job" value={<span className="text-[18px]">{ROLE_LABEL[player.primary]}</span>} accent={ROLE_COLOR[player.primary]} />
        <StatCard label="Jobs" metricKey="jobs" value={player.entropy.toFixed(2)} sub={player.pct.align_entropy != null ? `${ordinal(player.pct.align_entropy)} percentile` : undefined} />
        <StatCard label="Depth" metricKey="depth" value={`${player.depth.toFixed(1)} yd`} sub={player.pct.mean_depth != null ? `${ordinal(player.pct.mean_depth)} percentile` : undefined} />
        <StatCard label="In the Box" metricKey="box" value={pctOf(player.box)} sub={player.pct.box_rate != null ? `${ordinal(player.pct.box_rate)} percentile` : undefined} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_440px]">
        <div className="space-y-5">
          <div className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900 p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <div className="flex gap-1 rounded-lg border border-ink-700 bg-ink-900/40 p-0.5">
                {VIEWS.map((v) => (
                  <button key={v.key} type="button" onClick={() => setView(v.key)}
                    className={cn("rounded-md px-3 py-1.5 text-[13px] font-semibold transition-colors", v.key === view ? "bg-panthers-blue/20 text-panthers-bright" : "text-muted hover:text-white")}>{v.label}</button>
                ))}
              </div>
              {view !== "blocks" && (
                <div className="ml-auto flex gap-1">
                  {PLAY_FILTERS.map((f) => (
                    <button key={f.key} type="button" onClick={() => setFilter(f.key)}
                      className={cn("rounded-md px-2.5 py-1 text-[12px] font-semibold", f.key === filter ? "bg-white/[0.08] text-white" : "text-muted hover:text-white")}>{f.label}</button>
                  ))}
                </div>
              )}
            </div>
            {view !== "blocks" && view !== "heat" && (
              <div className="mb-3"><RoleLegend roles={roleOrder} active={active} onToggle={(r) => { const n = new Set(active); n.has(r) ? n.delete(r) : n.add(r); setActive(n); }} /></div>
            )}
            {!snaps ? <div className="aspect-[16/11] w-full animate-pulse rounded-xl bg-ink-800" /> : view === "map" ? (
              <AlignmentMap snaps={filtered} selected={picked} onPick={setPicked} active={active} />
            ) : view === "heat" ? (
              heat ? <HeatmapView snaps={filtered} heat={heat} peerKey={`${player.group}_${player.season}`} peerLabel={`${GROUP_LABEL[player.group]}, ${player.season}`} /> : <div className="text-sm text-muted">No data</div>
            ) : view === "move" ? (
              <MovementMap snaps={filtered} active={active} />
            ) : (
              <BlockMap blocks={player.blocks} />
            )}
            <p className="mt-2 text-[12px] text-muted">
              {view === "map" && `${filtered.length.toLocaleString("en-US")} snaps. Each dot is where he stood at the snap; faded dots are snaps a charter could call more than one way. Click one for its film.`}
              {view === "heat" && "Where he lined up, against every player at his position this season, on the same scale."}
              {view === "move" && "Each line runs from where he stood at the snap to where he was two seconds later, the window Eager & Seth measure bite and ground covered in."}
              {view === "blocks" && "From PFF's blocking chart on the snaps he was charted."}
            </p>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <div className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900 p-4">
              <div className="mb-2 text-[0.78rem] font-bold uppercase tracking-wide text-panthers-bright">Where He Lines Up</div>
              {roleOrder.map((r) => <ShareRow key={r} label={ROLE_LABEL[r]} value={player.align[r]} pct={player.pct[`share_${r}`]} color={ROLE_COLOR[r]} />)}
            </div>
            <div className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900 p-4">
              <div className="mb-2 text-[0.78rem] font-bold uppercase tracking-wide text-panthers-bright">What He Does After The Snap</div>
              {RESP.filter((r) => (player.resp[r] ?? 0) >= 0.005).map((r) => <ShareRow key={r} label={RESP_LABEL[r]} value={player.resp[r]} pct={player.pct[`resp_${r}`]} color={RESP_COLOR[r]} />)}
              <p className="mt-2 text-[12px] text-muted">PFF&apos;s charted assignment on every snap it charted one; the tracking model fills the rest.</p>
            </div>
          </div>

          {player.call && (
            <div className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900 p-4">
              <div className="mb-3 text-[0.78rem] font-bold uppercase tracking-wide text-panthers-bright">By The Call · One-High Vs Two-High</div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <StatCard label="Deep, one-high calls" value={pctOf(player.call.deep_share_one_high)} />
                <StatCard label="Deep, two-high calls" value={pctOf(player.call.deep_share_two_high)} />
                <StatCard label="Post safety, one-high" value={pctOf(player.call.middle_share_one_high)} />
                <StatCard label="Call explains" metricKey="call_explains" value={pctOf(player.call.call_explains)}
                  sub={(player.call.call_explains ?? 0) >= 0.5 ? "Mostly the call" : "Mostly his own deployment"} />
              </div>
            </div>
          )}
        </div>

        <div className="space-y-5">
          <FilmPanel snap={picked} playerName={player.name} />
          {snaps && <SnapList snaps={filtered} picked={picked} onPick={setPicked} />}
        </div>
      </div>
    </>
  );
}

/** Quick film: the most recent snaps at each of his jobs. */
function SnapList({ snaps, picked, onPick }: { snaps: Snap[]; picked: Snap | null; onPick: (s: Snap) => void }) {
  const byRole = useMemo(() => {
    const m = new Map<string, Snap[]>();
    for (const s of [...snaps].reverse()) { const a = m.get(s.role) ?? []; if (a.length < 4) a.push(s); m.set(s.role, a); }
    return [...m.entries()].sort((a, b) => ROLES.indexOf(a[0] as never) - ROLES.indexOf(b[0] as never));
  }, [snaps]);
  return (
    <div className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900 p-4">
      <div className="mb-2 text-[0.78rem] font-bold uppercase tracking-wide text-panthers-bright">Film By Job</div>
      {byRole.map(([role, list]) => (
        <div key={role} className="mb-2">
          <div className="mb-1 flex items-center gap-1.5 text-[12px] font-semibold text-muted"><span className="h-2 w-2 rounded-full" style={{ backgroundColor: ROLE_COLOR[role] }} />{ROLE_LABEL[role]}</div>
          <div className="flex flex-wrap gap-1">
            {list.map((s) => (
              <button key={`${s.game_key}-${s.play_id}`} type="button" onClick={() => onPick(s)}
                className={cn("rounded-md border px-2 py-1 text-[12px] transition-colors", picked?.play_id === s.play_id && picked?.game_key === s.game_key ? "border-panthers-bright bg-panthers-blue/20 text-white" : "border-ink-700 text-foreground hover:bg-ink-800")}>
                Week {s.week} {s.opp ?? ""} · {downDistance(s.down, s.distance)}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Page() {
  return <Suspense fallback={<CardsSkeleton count={4} />}><PlayerRoom /></Suspense>;
}
