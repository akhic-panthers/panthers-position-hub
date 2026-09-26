"use client";
// Film for one snap, from Thunder (XOS). The server route holds the credential and returns signed CloudFront URLs
// with the snap's seek window; the browser only ever sees the video.
import { useEffect, useRef, useState } from "react";
import { Clapperboard } from "lucide-react";
import type { Snap } from "@/lib/ph";
import { ROLE_LABEL, downDistance } from "@/lib/roles";
import { cn } from "@/lib/utils";

type Angle = { view: string; label: string; url: string; start: number; end: number };
type Film = { title: string; description: string | null; angles: Angle[] };

export function FilmPanel({ snap, playerName }: { snap: Snap | null; playerName: string }) {
  const [film, setFilm] = useState<Film | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState("EZ");
  const video = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (!snap) return;
    let dead = false;
    setLoading(true); setErr(null); setFilm(null);
    fetch(`/api/film?game_key=${snap.game_key}&play_id=${snap.play_id}`)
      .then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.error ?? `HTTP ${r.status}`); return j as Film; })
      .then((f) => { if (!dead) { setFilm(f); if (!f.angles.some((a) => a.view === view)) setView(f.angles[0]?.view ?? "EZ"); } })
      .catch((e) => { if (!dead) setErr(e.message); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snap?.game_key, snap?.play_id]);

  const angle = film?.angles.find((a) => a.view === view) ?? film?.angles[0];

  // keep playback inside the snap's window
  useEffect(() => {
    const v = video.current;
    if (!v || !angle) return;
    const onTime = () => { if (v.currentTime > angle.end) { v.pause(); v.currentTime = angle.start; } };
    v.addEventListener("timeupdate", onTime);
    return () => v.removeEventListener("timeupdate", onTime);
  }, [angle]);

  return (
    <div className="rounded-xl border border-ink-700 bg-gradient-to-br from-ink-850 to-ink-900">
      <div className="flex items-center gap-2 border-b border-ink-700 bg-ink-800 px-4 py-2.5 text-[0.78rem] font-bold uppercase tracking-wide text-panthers-bright">
        <Clapperboard className="h-4 w-4" /> Film
      </div>
      <div className="p-4">
        {!snap && <p className="text-[13px] text-muted">Pick any snap on the field to pull its film from Thunder, every angle, cued to the snap.</p>}
        {snap && (
          <div className="mb-3">
            <div className="text-[15px] font-bold text-white">{playerName} · Week {snap.week} vs {snap.opp ?? "—"}</div>
            <div className="text-[13px] text-muted">{downDistance(snap.down, snap.distance)} · {snap.pa ? "Play action" : snap.pass ? "Pass" : "Run"} · lined up as {ROLE_LABEL[snap.role]} ({Math.round(snap.p * 100)}%)</div>
          </div>
        )}
        {loading && <div className="aspect-video w-full animate-pulse rounded-lg bg-ink-800" />}
        {err && <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-[13px] text-rose-200">{err}</div>}
        {film && angle && (
          <>
            <div className="mb-2 flex flex-wrap gap-1">
              {film.angles.map((a) => (
                <button key={a.view} type="button" onClick={() => setView(a.view)}
                  className={cn("rounded-lg px-2.5 py-1 text-[12px] font-semibold transition-colors",
                    a.view === angle.view ? "bg-panthers-blue/20 text-panthers-bright" : "text-muted hover:bg-white/[0.06] hover:text-white")}>
                  {a.label}
                </button>
              ))}
            </div>
            <video ref={video} key={`${angle.url}#${angle.start}`} src={`${angle.url}#t=${angle.start.toFixed(2)},${angle.end.toFixed(2)}`}
              controls autoPlay muted playsInline preload="metadata" className="aspect-video w-full rounded-lg bg-black"
              onLoadedMetadata={(e) => { (e.currentTarget as HTMLVideoElement).currentTime = angle.start; }} />
            {film.description && <p className="mt-2 text-[13px] leading-snug text-[#aab5bf]">{film.description}</p>}
          </>
        )}
      </div>
    </div>
  );
}
