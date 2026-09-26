"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { HeroIntro } from "@/components/nav/hero-intro";
import { Select } from "@/components/ui/select";
import { TableSkeleton, ErrorState, EmptyState } from "@/components/ui/states";
import { TeamLogo } from "@/components/ui/team-logo";
import { PlayerHeadshot } from "@/components/ph/headshot";
import { MixBar, RoleLegend } from "@/components/ph/role-bars";
import { MetricHeader } from "@/components/ui/metric-header";
import { loadIndex, type Index, type PlayerSeason } from "@/lib/ph";
import { GROUP_LABEL, GROUP_ROLES, ROLE_LABEL, ROLES, ordinal } from "@/lib/roles";
import { cn } from "@/lib/utils";

const GROUPS = ["S", "CB", "LB", "EDGE", "IDL"];

function Board() {
  const q = useSearchParams();
  const router = useRouter();
  const [data, setData] = useState<Index | null>(null);
  const [err, setErr] = useState<Error | null>(null);
  const [search, setSearch] = useState("");
  useEffect(() => { loadIndex().then(setData).catch(setErr); }, []);

  const seasons = useMemo(() => (data ? [...new Set(data.players.map((p) => p.season))].sort((a, b) => b - a) : []), [data]);
  const season = Number(q.get("season")) || seasons[0];
  const group = q.get("group") ?? (q.get("team") ? "" : "S");
  const team = q.get("team") ?? "";
  const sortRole = q.get("sort") ?? (group ? GROUP_ROLES[group]?.[0] : "") ?? "";
  const teams = useMemo(() => (data ? [...new Set(data.players.map((p) => p.team).filter(Boolean))].sort() : []), [data]);

  const set = (k: string, v: string) => {
    const n = new URLSearchParams(q.toString());
    if (v) n.set(k, v); else n.delete(k);
    if (k === "group") n.delete("sort");
    router.replace(`/?${n.toString()}`, { scroll: false });
  };

  const rows = useMemo(() => {
    if (!data) return [];
    const s = search.trim().toLowerCase();
    return data.players
      .filter((p) => p.season === season && (!group || p.group === group) && (!team || p.team === team) && (!s || p.name?.toLowerCase().includes(s)))
      .sort((a, b) => (sortRole ? (b.align[sortRole] ?? 0) - (a.align[sortRole] ?? 0) : b.snaps - a.snaps));
  }, [data, season, group, team, search, sortRole]);

  const roleCols = (group ? GROUP_ROLES[group] : ROLES.slice()).slice(0, 5);

  return (
    <>
      <HeroIntro eyebrow="Position Hub · 2022–2025" lead="What He" accent="Actually Plays"
        sub="PFF charts one position per snap. This reads every snap from the tracking and asks how a charter would call it, so a safety shows up as the post, half-field, box and slot man he really is."
        chips={["1.6M Defensive Snaps", "Every Snap On Film", "Deployment, Not A Grade"]} />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-wrap gap-1 rounded-lg border border-ink-700 bg-ink-900/40 p-0.5">
          {GROUPS.map((g) => (
            <button key={g} type="button" onClick={() => set("group", g === group ? "" : g)}
              className={cn("rounded-md px-3 py-1.5 text-[13px] font-semibold transition-colors", g === group ? "bg-panthers-blue/20 text-panthers-bright" : "text-muted hover:text-white")}>
              {GROUP_LABEL[g]}
            </button>
          ))}
        </div>
        <div className="w-32"><Select label="Season" value={season ?? ""} onChange={(e) => set("season", e.target.value)}>{seasons.map((s) => <option key={s}>{s}</option>)}</Select></div>
        <div className="w-36"><Select label="Team" value={team} onChange={(e) => set("team", e.target.value)}><option value="">All teams</option>{teams.map((t) => <option key={t}>{t}</option>)}</Select></div>
        <label className="flex flex-col gap-1.5">
          <span className="text-[0.68rem] font-bold uppercase tracking-wider text-panthers-bright">Player</span>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by name"
            className="w-56 rounded-lg border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-foreground outline-none focus:border-panthers-blue" />
        </label>
        <div className="ml-auto"><RoleLegend /></div>
      </div>

      {err ? <ErrorState error={err} /> : !data ? <TableSkeleton rows={12} /> : rows.length === 0 ? (
        <EmptyState title="No players" message="Nobody at this position cleared 100 snaps with these filters." />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-ink-700">
          <table className="w-full text-sm">
            <thead className="bg-[#101820]">
              <tr className="border-b-2 border-panthers-blue text-left text-[0.7rem] font-bold uppercase tracking-wide text-panthers-bright">
                <th className="px-3 py-2.5">Player</th>
                <th className="px-3 py-2.5">Team</th>
                <th className="px-3 py-2.5 text-right"><MetricHeader label="Snaps" metricKey="snaps" /></th>
                <th className="min-w-[220px] px-3 py-2.5"><MetricHeader label="Role Mix" metricKey="role_mix" /></th>
                {roleCols.map((r) => (
                  <th key={r} className="px-3 py-2.5 text-right">
                    <button type="button" onClick={() => set("sort", r)} className={cn("uppercase", sortRole === r ? "text-white" : "hover:text-white")}>{ROLE_LABEL[r]}</button>
                  </th>
                ))}
                <th className="px-3 py-2.5 text-right"><MetricHeader label="Jobs" metricKey="jobs" /></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => <Row key={`${p.id}-${p.season}`} p={p} roleCols={roleCols} />)}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 text-[12px] text-muted">Shares describe where a man lined up on his snaps this season. They rate deployment, not play. Percentiles are against his position group, same season, 200 snaps or more.</p>
    </>
  );
}

function Row({ p, roleCols }: { p: PlayerSeason; roleCols: string[] }) {
  return (
    <tr className="border-b border-ink-800 transition-colors hover:bg-ink-800/60">
      <td className="px-3 py-2">
        <Link href={`/player?id=${p.id}&season=${p.season}`} className="flex items-center gap-2.5">
          <PlayerHeadshot name={p.name} url={p.head} size={32} />
          <span><span className="block font-semibold text-white hover:text-panthers-bright">{p.name}</span><span className="text-[12px] text-muted">{p.pos}</span></span>
        </Link>
      </td>
      <td className="px-3 py-2"><TeamLogo team={p.team} size={20} /></td>
      <td className="tnum px-3 py-2 text-right text-foreground">{p.snaps.toLocaleString("en-US")}</td>
      <td className="px-3 py-2"><MixBar align={p.align} /></td>
      {roleCols.map((r) => (
        <td key={r} className="tnum px-3 py-2 text-right">
          <span className="font-semibold text-white">{Math.round((p.align[r] ?? 0) * 100)}%</span>
          {p.pct[`share_${r}`] != null && <span className="ml-1.5 text-[11px] text-muted">{ordinal(p.pct[`share_${r}`])}</span>}
        </td>
      ))}
      <td className="tnum px-3 py-2 text-right text-foreground">{p.entropy?.toFixed(2)}</td>
    </tr>
  );
}

export default function Page() {
  return <Suspense fallback={<TableSkeleton rows={12} />}><Board /></Suspense>;
}
