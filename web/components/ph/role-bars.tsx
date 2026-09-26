import { cn } from "@/lib/utils";
import { ANY_ROLE_COLOR as ROLE_COLOR, ANY_ROLE_LABEL as ROLE_LABEL, ROLES, ordinal } from "@/lib/roles";

/** One stacked bar for a whole role mix. 2px surface gap between touching fills (mark spec). */
export function MixBar({ align, roles = ROLES, className, height = 10 }: { align: Record<string, number | null>; roles?: readonly string[]; className?: string; height?: number }) {
  return (
    <div className={cn("flex w-full gap-[2px] overflow-hidden rounded-[4px]", className)} style={{ height }}>
      {roles.map((r) => {
        const v = align[r] ?? 0;
        return v >= 0.01 ? <span key={r} title={`${ROLE_LABEL[r]} ${(v * 100).toFixed(0)}%`} style={{ width: `${v * 100}%`, backgroundColor: ROLE_COLOR[r] }} /> : null;
      })}
    </div>
  );
}

export function RoleLegend({ roles = ROLES as readonly string[], active, onToggle }: { roles?: readonly string[]; active?: Set<string>; onToggle?: (r: string) => void }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1.5">
      {roles.map((r) => {
        const on = !active || active.has(r);
        return (
          <button key={r} type="button" onClick={onToggle ? () => onToggle(r) : undefined} disabled={!onToggle}
            className={cn("inline-flex items-center gap-1.5 text-[12px] font-semibold transition-opacity", on ? "text-foreground" : "text-muted opacity-50", onToggle && "cursor-pointer hover:text-white")}>
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: ROLE_COLOR[r] }} />
            {ROLE_LABEL[r] ?? r}
          </button>
        );
      })}
    </div>
  );
}

/** Label · bar (≤14px, 4px rounded data end) · share · percentile. Text never wears the series color. */
export function ShareRow({ label, value, pct, color }: { label: string; value: number | null; pct?: number | null; color: string }) {
  const v = value ?? 0;
  return (
    <div className="grid grid-cols-[170px_1fr_52px_64px] items-center gap-3 py-1">
      <span className="flex items-center gap-2 text-[13px] text-foreground">
        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />{label}
      </span>
      <div className="h-3 overflow-hidden rounded-r-[4px] bg-ink-900">
        <div className="h-full rounded-r-[4px]" style={{ width: `${Math.max(v * 100, v > 0 ? 1 : 0)}%`, backgroundColor: color }} />
      </div>
      <span className="tnum text-right text-[13px] font-bold text-white">{(v * 100).toFixed(0)}%</span>
      <span className="tnum text-right text-[12px] text-muted" title="Percentile against his position group, same season">
        {pct == null ? "" : ordinal(pct)}
      </span>
    </div>
  );
}
