"use client";
import * as React from "react";
import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import { Button } from "./button";
import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-md bg-ink-800", className)} {...props} />;
}

export function TableSkeleton({ rows = 10 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      <Skeleton className="h-10 w-full" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-9 w-full" style={{ opacity: 1 - i * 0.04 }} />
      ))}
    </div>
  );
}

export function CardsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-28 w-full" />
      ))}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry?: () => void;
}) {
  const api = null as null | { status?: number; message?: string; endpoint?: string };
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-tier-low/40 bg-tier-low/5 px-6 py-10 text-center">
      <AlertTriangle className="h-8 w-8 text-tier-low" />
      <div className="text-base font-semibold text-foreground">
        {api ? `API error (${api.status || "network"})` : "Something went wrong"}
      </div>
      <p className="max-w-md text-sm text-muted">
        {error instanceof Error ? error.message : "Failed to load data."}
        {api?.endpoint && (
          <span className="mt-1 block font-mono text-xs text-muted/70">{api.endpoint}</span>
        )}
      </p>
      <div className="flex gap-2">
        {onRetry && (
          <Button variant="outline" onClick={onRetry}>
            <RefreshCw className="h-4 w-4" /> Retry
          </Button>
        )}
        <a
          href="/methodology"
          className="inline-flex items-center rounded-lg border border-ink-700 px-4 py-2 text-sm text-muted hover:text-foreground"
        >
          Methodology
        </a>
      </div>
    </div>
  );
}

export function EmptyState({ title, message }: { title: string; message?: string }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-ink-700 bg-card px-6 py-12 text-center">
      <Inbox className="h-8 w-8 text-muted" />
      <div className="text-base font-semibold text-foreground">{title}</div>
      {message && <p className="max-w-md text-sm text-muted">{message}</p>}
    </div>
  );
}
