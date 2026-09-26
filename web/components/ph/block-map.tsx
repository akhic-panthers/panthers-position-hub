// The block map, from PFF's blocking chart: which gap he was assigned, who blocked him, how, and — for rushers —
// which move he used. PFF's gap letters are folded left/right (the mirror image of a gap is the same gap). Codes are
// PFF's own definitions (PFF Data Reference Guide, "All Blocking Codes"), never paraphrased from memory.
import type { Blocks } from "@/lib/ph";
import { pctOf } from "@/lib/ph";
import { cn } from "@/lib/utils";


function Bars({ title, data, total, max = 7, color = "#1CA3E0" }: { title: string; data: Record<string, number>; total?: number; max?: number; color?: string }) {
  const rows = Object.entries(data).sort((a, b) => b[1] - a[1]).slice(0, max);
  const sum = total ?? rows.reduce((a, [, v]) => a + v, 0);
  if (!rows.length) return (
    <div><div className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted">{title}</div><div className="text-sm text-muted">No data</div></div>
  );
  return (
    <div>
      <div className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted">{title}</div>
      {rows.map(([k, v]) => (
        <div key={k} className="grid grid-cols-[150px_1fr_46px] items-center gap-2 py-[3px]">
          <span className="truncate text-[13px] text-foreground">{k}</span>
          <div className="h-3 overflow-hidden rounded-r-[4px] bg-ink-900"><div className="h-full rounded-r-[4px]" style={{ width: `${(v / sum) * 100}%`, backgroundColor: color }} /></div>
          <span className="tnum text-right text-[12px] font-semibold text-white">{Math.round((v / sum) * 100)}%</span>
        </div>
      ))}
    </div>
  );
}

/** One folded half of the line, center out, the way PFF names the gaps: A (center–guard), B (guard–tackle),
 *  C (outside the tackle), D (between the first and second tight end), E (second–third), then outside the widest TE. */
function GapLane({ gaps }: { gaps: Record<string, number> }) {
  const sum = Object.values(gaps).reduce((a, b) => a + b, 0) || 1;
  const seq: ({ man: string } | { gap: string; label: string })[] = [
    { man: "C" }, { gap: "A gap", label: "A" }, { man: "G" }, { gap: "B gap", label: "B" }, { man: "T" }, { gap: "C gap", label: "C" },
    { man: "TE" }, { gap: "D gap", label: "D" }, { man: "TE" }, { gap: "E gap", label: "E" }, { man: "TE" }, { gap: "Outside the widest TE", label: "Edge" },
  ];
  return (
    <div>
      <div className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted">Gap he was assigned · center out, both sides folded</div>
      <div className="flex items-end gap-[2px]">
        {seq.map((c, i) => "man" in c ? (
          <div key={i} className="flex h-10 w-9 shrink-0 items-center justify-center rounded-md border border-ink-600 bg-ink-800 text-[11px] font-bold text-muted">{c.man}</div>
        ) : (
          <div key={i} className="flex min-w-0 flex-1 flex-col items-center">
            <span className="tnum mb-1 text-[12px] font-bold text-white">{gaps[c.gap] ? `${Math.round((gaps[c.gap] / sum) * 100)}%` : ""}</span>
            <div className="h-10 w-full rounded-md" style={{ backgroundColor: `rgba(28,163,224,${Math.min(1, 0.06 + ((gaps[c.gap] ?? 0) / sum) * 1.6).toFixed(3)})` }} />
            <span className="mt-1 text-[11px] font-semibold text-muted">{c.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900 p-3.5">
      <div className="text-[0.68rem] font-bold uppercase tracking-wider text-muted">{label}</div>
      <div className="tnum mt-1 text-xl font-extrabold text-white">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  );
}

export function BlockMap({ blocks, className }: { blocks: Blocks | null; className?: string }) {
  if (!blocks || !blocks.charted_snaps) return <div className="flex h-40 items-center justify-center text-sm text-muted">No data</div>;
  const blocked = Object.values(blocks.blockers).reduce((a, b) => a + b, 0);
  const hasGaps = Object.keys(blocks.gaps).length > 0;
  return (
    <div className={cn("space-y-5", className)}>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile label="Charted snaps" value={blocks.charted_snaps.toLocaleString("en-US")} sub="in PFF's blocking chart" />
        <Tile label="Double teamed" value={pctOf(blocks.double_team_rate)} sub="of snaps he was blocked" />
        <Tile label="Unblocked" value={pctOf(blocks.unblocked_rate)} sub="never touched by a blocker" />
        <Tile label="Looper on a stunt" value={pctOf(blocks.looper_rate)} sub="second man through the game" />
      </div>
      {hasGaps && <GapLane gaps={blocks.gaps} />}
      <div className="grid gap-6 md:grid-cols-2">
        <Bars title="Who blocked him" data={blocks.blockers} total={blocked} />
        <Bars title="How they blocked him" data={blocks.types} />
        {Object.keys(blocks.moves).length > 0 && <Bars title="His first rush move" data={blocks.moves} color="#F43F5E" />}
        {Object.keys(blocks.jobs).length > 0 && <Bars title="Run support job" data={blocks.jobs} color="#22D3EE" />}
      </div>
    </div>
  );
}
