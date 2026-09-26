import { MetricHeader } from "@/components/ui/metric-header";
import { cn } from "@/lib/utils";
import * as React from "react";

export function StatCard({
  label,
  metricKey,
  value,
  sub,
  accent,
  className,
  flag,
  flagTitle,
}: {
  label: string;
  metricKey?: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  accent?: string;
  className?: string;
  flag?: React.ReactNode;
  flagTitle?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900 p-4",
        className,
      )}
      style={accent ? { borderTopColor: accent, borderTopWidth: 3 } : undefined}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="text-[0.68rem] font-bold uppercase tracking-wider text-muted">
          {metricKey ? <MetricHeader label={label} metricKey={metricKey} /> : label}
        </div>
        {flag != null && (
          <span className="text-lg leading-none text-amber-400" title={flagTitle}>
            {flag}
          </span>
        )}
      </div>
      <div className="tnum mt-1 text-2xl font-extrabold text-white">{value}</div>
      {sub && <div className="tnum mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  );
}
