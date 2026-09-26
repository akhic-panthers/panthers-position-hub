import { cn } from "@/lib/utils";
import { TIER_COLORS, TIER_LABEL } from "@/lib/constants";
import * as React from "react";

export function Badge({
  className,
  color,
  children,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { color?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        className,
      )}
      style={color ? { backgroundColor: `${color}22`, color, border: `1px solid ${color}55` } : undefined}
      {...props}
    >
      {children}
    </span>
  );
}

export function TierBadge({ tier }: { tier: string }) {
  const color = TIER_COLORS[tier] ?? "#8A949C";
  return (
    <Badge color={color} title={TIER_LABEL[tier] ?? tier}>
      {tier}
    </Badge>
  );
}
