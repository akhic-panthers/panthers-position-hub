import { cn } from "@/lib/utils";
import { ChevronDown } from "lucide-react";
import * as React from "react";

// Lightweight native-select wrapper styled for the dark theme.
export function Select({
  className,
  label,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement> & { label?: string }) {
  return (
    <label className="flex flex-col gap-1.5">
      {label && (
        <span className="text-[0.68rem] font-bold uppercase tracking-wider text-panthers-bright">
          {label}
        </span>
      )}
      <div className="relative">
        <select
          className={cn(
            "w-full appearance-none rounded-lg border border-ink-700 bg-ink-800 px-3 py-2 pr-9 text-sm text-foreground outline-none focus:border-panthers-blue",
            className,
          )}
          {...props}
        >
          {children}
        </select>
        <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
      </div>
    </label>
  );
}
