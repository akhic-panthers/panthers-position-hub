"use client";
/* eslint-disable @next/next/no-img-element */
// The sister app's PlayerHeadshot, minus its API lookup: the export already carries the ESPN headshot URL
// (web/public/phase11_players.json in panthers_projects, keyed by nfl_id). Initials when there is none.
import { useState } from "react";
import { cn } from "@/lib/utils";

export function PlayerHeadshot({ name, url, size = 64, className }: { name: string; url?: string | null; size?: number; className?: string }) {
  const [failed, setFailed] = useState(false);
  const initials = (name ?? "").split(" ").map((n) => n[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();
  const box = cn("relative shrink-0 overflow-hidden rounded-full bg-ink-900 ring-1 ring-ink-700", className);
  if (!url || failed) {
    return (
      <div className={cn(box, "flex items-center justify-center font-extrabold text-panthers-bright")} style={{ width: size, height: size, fontSize: Math.max(12, size * 0.28) }} aria-label={name}>
        {initials || "?"}
      </div>
    );
  }
  return (
    <div className={box} style={{ width: size, height: size }} aria-label={name}>
      <img src={url} alt="" className="h-full w-full object-cover object-top" onError={() => setFailed(true)} />
    </div>
  );
}
