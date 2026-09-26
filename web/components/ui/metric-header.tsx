"use client";

import { Info } from "lucide-react";
import { MetricPopover } from "@/components/ui/metric-popover";
import { memo, useEffect, useRef, useState } from "react";
import { getMetricDefinition, getMetricTip } from "@/lib/metric-definitions";
import { cn } from "@/lib/utils";

function MetricHeaderInner({
  label,
  metricKey,
  className,
}: {
  label: string;
  metricKey?: string;
  className?: string;
}) {
  const key = metricKey ?? label;
  const def = getMetricDefinition(key);
  const tip = getMetricTip(key);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      const t = e.target as Node;
      if (wrapRef.current?.contains(t)) return;
      if ((t as Element).closest?.('[role="tooltip"]')) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (!tip && !def) {
    return <span className={className}>{label}</span>;
  }

  const directionLabel =
    def?.direction === "higher"
      ? "↑ higher is better"
      : def?.direction === "lower"
        ? "↓ lower is better"
        : null;

  return (
    <span ref={wrapRef} className={cn("relative inline-flex", className)}>
      <button
        type="button"
        aria-expanded={open}
        aria-label={`About ${label}`}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className="inline-flex cursor-help items-center gap-1 rounded border-b border-dotted border-muted/80 bg-transparent p-0 text-left hover:text-white"
      >
        {label}
        <Info className="h-3.5 w-3.5 shrink-0 opacity-70" />
      </button>
      <MetricPopover open={open} anchorRef={wrapRef}>
        {def?.short && <span className="mb-1.5 block font-semibold text-panthers-bright">{def.short}</span>}
        <span className="block text-foreground/90">{tip}</span>
        {directionLabel && <span className="mt-2 block text-[0.65rem] text-muted">{directionLabel}</span>}
      </MetricPopover>
    </span>
  );
}

export const MetricHeader = memo(MetricHeaderInner);
