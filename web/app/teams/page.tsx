"use client";
import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/nav/section-badge";
import { Select } from "@/components/ui/select";
import { TeamLogo } from "@/components/ui/team-logo";
import { ErrorState, TableSkeleton } from "@/components/ui/states";
import { loadTeams, pctOf } from "@/lib/ph";
import { cn } from "@/lib/utils";

type Row = { defense_team: string; season: number; down_group: string; distance_group: string; plays: number;
  one_high_or_zero: number; two_high: number; pff_played_open: number };
const DOWNS = ["1st/2nd down", "3rd down", "4th down"];
const DISTS = ["short (1–3)", "medium (4–7)", "long (8+)"];

export default function Teams() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [err, setErr] = useState<Error | null>(null);
  const [season, setSeason] = useState(2025);
  const [down, setDown] = useState("1st/2nd down");
  const [dist, setDist] = useState("long (8+)");
  useEffect(() => { loadTeams().then((r) => setRows(r as Row[])).catch(setErr); }, []);
  const shown = useMemo(() => (rows ?? []).filter((r) => r.season === season && r.down_group === down && r.distance_group === dist)
    .sort((a, b) => b.two_high - a.two_high), [rows, season, down, dist]);
  const seasons = useMemo(() => [...new Set((rows ?? []).map((r) => r.season))].sort((a, b) => b - a), [rows]);
  return (
    <>
      <PageHeader section="defense" badge="Team Shells" title="How They Deploy"
        subtitle="Two deep, one deep or zero at the snap, by down and distance, next to PFF's charted middle-of-the-field call. Teams with fewer than 100 plays in the situation are left out." />
      <div className="mb-4 flex flex-wrap gap-3">
        <div className="w-32"><Select label="Season" value={season} onChange={(e) => setSeason(Number(e.target.value))}>{seasons.map((s) => <option key={s}>{s}</option>)}</Select></div>
        <div className="w-44"><Select label="Down" value={down} onChange={(e) => setDown(e.target.value)}>{DOWNS.map((d) => <option key={d}>{d}</option>)}</Select></div>
        <div className="w-44"><Select label="Distance" value={dist} onChange={(e) => setDist(e.target.value)}>{DISTS.map((d) => <option key={d}>{d}</option>)}</Select></div>
      </div>
      {err ? <ErrorState error={err} /> : !rows ? <TableSkeleton rows={12} /> : (
        <div className="overflow-x-auto rounded-xl border border-ink-700">
          <table className="w-full text-sm">
            <thead className="bg-[#101820]">
              <tr className="border-b-2 border-panthers-blue text-left text-[0.7rem] font-bold uppercase tracking-wide text-panthers-bright">
                <th className="px-3 py-2.5">Defense</th><th className="px-3 py-2.5 text-right">Plays</th>
                <th className="min-w-[260px] px-3 py-2.5">Two High At The Snap</th>
                <th className="px-3 py-2.5 text-right">One High Or Zero</th><th className="px-3 py-2.5 text-right">PFF: Middle Played Open</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.defense_team} className={cn("border-b border-ink-800", r.defense_team === "CAR" && "bg-panthers-blue/10")}>
                  <td className="px-3 py-2"><TeamLogo team={r.defense_team} size={20} /></td>
                  <td className="tnum px-3 py-2 text-right">{r.plays.toLocaleString("en-US")}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div className="h-3 flex-1 overflow-hidden rounded-r-[4px] bg-ink-900"><div className="h-full rounded-r-[4px] bg-[#22D3EE]" style={{ width: `${r.two_high * 100}%` }} /></div>
                      <span className="tnum w-10 text-right font-semibold text-white">{pctOf(r.two_high)}</span>
                    </div>
                  </td>
                  <td className="tnum px-3 py-2 text-right">{pctOf(r.one_high_or_zero)}</td>
                  <td className="tnum px-3 py-2 text-right">{pctOf(r.pff_played_open)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 text-[12px] text-muted">Deep means a defender at 10 yards or more when the ball is snapped. PFF&apos;s call is the shell played after the snap, so the two columns differ exactly where a defense rotates.</p>
    </>
  );
}
