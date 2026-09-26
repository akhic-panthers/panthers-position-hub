"use client";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/nav/section-badge";
import { ErrorState, TableSkeleton } from "@/components/ui/states";
import { loadGates } from "@/lib/ph";
import { cn } from "@/lib/utils";

type Gate = { name: string; value: number | string | null; bar: number | string | null; pass: boolean | null; n: number; note?: string };
const TITLES: Record<string, string> = {
  "2026-09-26_v2/gates_v2": "Role Model v2 · Trained On PFF's Charted Slot",
  "2026-09-25_full/gates": "Role Model v1 · First Run",
  "2026-09-25_full/extensions_gates": "Extensions · Bite, Ground Covered, Disguise, Match, Offense",
};

function fmt(v: unknown) { return v == null ? "—" : typeof v === "number" ? v.toFixed(3) : String(v); }

export default function Method() {
  const [g, setG] = useState<Record<string, Gate[]> | null>(null);
  const [err, setErr] = useState<Error | null>(null);
  useEffect(() => { loadGates().then((x) => setG(x as unknown as Record<string, Gate[]>)).catch(setErr); }, []);
  return (
    <>
      <PageHeader section="neutral" badge="Method" title="Every Bar, Written Before The Numbers"
        subtitle="Each gate was registered in the repo before the model it judges was run. A miss ships as a finding. The role mix rates deployment; it is not a grade and not a projection." subtitleClassName="max-w-4xl" />
      {err ? <ErrorState error={err} /> : !g ? <TableSkeleton rows={10} /> : (
        <div className="space-y-6">
          {Object.entries(TITLES).filter(([k]) => g[k]).map(([k, title]) => (
            <div key={k} className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900">
              <div className="rounded-t-xl border-b border-ink-700 bg-ink-800 px-5 py-3 text-[0.78rem] font-bold uppercase tracking-wide text-panthers-bright">{title}</div>
              <table className="w-full text-sm">
                <tbody>
                  {g[k].map((x) => (
                    <tr key={x.name} className="border-b border-ink-800 align-top">
                      <td className="px-4 py-2.5 font-semibold text-white">{x.name.replace(/_/g, " ")}</td>
                      <td className="tnum px-4 py-2.5 text-right text-white">{fmt(x.value)}</td>
                      <td className="tnum px-4 py-2.5 text-right text-muted">{fmt(x.bar)}</td>
                      <td className="px-4 py-2.5">
                        {(() => {
                          const v = x.pass == null ? (String(x.note ?? "").startsWith("VOID") ? "VOID" : "—") : x.pass ? "GO" : "NO-GO";
                          return <span className={cn("rounded-full border px-2.5 py-0.5 text-[11px] font-bold", v === "GO" ? "border-emerald-500/40 bg-emerald-500/20 text-emerald-300" : v === "NO-GO" ? "border-rose-500/40 bg-rose-500/20 text-rose-300" : "border-ink-600 bg-ink-800 text-muted")}>{v}</span>;
                        })()}
                      </td>
                      <td className="max-w-[520px] px-4 py-2.5 text-[12px] text-muted">{x.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
