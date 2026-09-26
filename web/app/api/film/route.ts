import { NextResponse } from "next/server";
import { filmForPlay } from "@/lib/server/thunder";

export const dynamic = "force-dynamic";

// GET /api/film?game_key=59848&play_id=2802 → every angle of that snap, seek times in seconds.
export async function GET(req: Request) {
  const q = new URL(req.url).searchParams;
  const gameKey = Number(q.get("game_key")), playId = Number(q.get("play_id"));
  if (!Number.isFinite(gameKey) || !Number.isFinite(playId)) return NextResponse.json({ error: "game_key and play_id are required" }, { status: 400 });
  try {
    const film = await filmForPlay(gameKey, playId);
    if (!film) return NextResponse.json({ error: "Thunder has no film for this snap" }, { status: 404 });
    return NextResponse.json(film, { headers: { "Cache-Control": "private, max-age=3600" } });
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : "film lookup failed" }, { status: 502 });
  }
}
