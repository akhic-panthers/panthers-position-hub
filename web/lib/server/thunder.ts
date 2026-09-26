import "server-only";
// Thunder (XOS / Catapult film), server side only. The credential never reaches the browser; the browser gets
// signed CloudFront URLs (valid ~1 day) and seek times. Measured 2026-09-26 with the club's Thunder login:
//   SearchForPlaysComplex(GSIS.GameKey = g, includeClips) → every play of the game, each carrying PFF's own keys
//   (PFF.pff_GSISPLAYID = our gsis_play_id) and one clip per angle (SB SL EZ EZ2 TV) as a frame range inside a
//   full-game MP4 at 59.94 fps; GetURLsForElement(MediaReferenceId) → the signed MP4 URL.
//   Seek = MediaFrameStart / FPS — confirmed by eye in the app on 2026-09-26 (film starts at the snap).
// Auth is `Authorization: API base64(user:pass)` — not Basic, not Bearer (sister repo evaluation/THUNDER.md).
import fs from "node:fs";
import path from "node:path";

const BASE = "https://tclightningservices.xosdigital.com/Api/ThunderAPI";

function credential(): { user: string; pass: string } | null {
  let user = process.env.THUNDER_USERNAME ?? "";
  let pass = process.env.THUNDER_PASSWORD ?? "";
  if (!user || !pass) {
    // one place for secrets: the repo-root .env that the Python side reads (gitignored)
    const p = path.resolve(process.cwd(), "..", ".env");
    if (fs.existsSync(p)) {
      for (const line of fs.readFileSync(p, "utf8").split("\n")) {
        const m = line.match(/^\s*(THUNDER_USERNAME|THUNDER_PASSWORD)\s*=\s*(.*)\s*$/);
        if (!m) continue;
        const v = m[2].replace(/^['"]|['"]$/g, "");
        if (m[1] === "THUNDER_USERNAME" && !user) user = v;
        if (m[1] === "THUNDER_PASSWORD" && !pass) pass = v;
      }
    }
  }
  return user && pass ? { user, pass } : null;
}

async function call<T>(endpoint: string, params: Record<string, string>): Promise<T> {
  const cred = credential();
  if (!cred) throw new Error("no Thunder credential: set THUNDER_USERNAME / THUNDER_PASSWORD in the repo .env");
  const url = `${BASE}/${endpoint}?${new URLSearchParams(params)}`;
  const r = await fetch(url, {
    headers: { Accept: "application/json", Authorization: "API " + Buffer.from(`${cred.user}:${cred.pass}`).toString("base64") },
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`Thunder ${endpoint} HTTP ${r.status}`);   // a bad credential is a 500 here, not a 401
  return r.json() as Promise<T>;
}

type Clip = { ViewId: string; MediaReferenceId: string; MediaFrameStart: number; MediaFrameEnd: number; FPS: number };
type TCPlay = { Id: string; Name: string; PlayFieldValues: Record<string, string>; Clips: Clip[] | null; ViewList: { Id: string; Name: string }[] | null };

export type FilmAngle = { view: string; label: string; url: string; start: number; end: number };
export type FilmPlay = { gameKey: number; playId: number; title: string; description: string | null; angles: FilmAngle[] };

const VIEW_LABEL: Record<string, string> = { SL: "Sideline", EZ: "End Zone", EZ2: "End Zone 2", TV: "Broadcast", SB: "Scoreboard" };
const VIEW_ORDER = ["EZ", "SL", "TV", "EZ2", "SB"];

const GAME_TTL = 30 * 60_000, URL_TTL = 12 * 3_600_000;
const games = new Map<number, { at: number; plays: Promise<Map<number, TCPlay>> }>();
const urls = new Map<string, { at: number; url: Promise<string | null> }>();

function gamePlays(gameKey: number): Promise<Map<number, TCPlay>> {
  const hit = games.get(gameKey);
  if (hit && Date.now() - hit.at < GAME_TTL) return hit.plays;
  const xml = `<criterias><criteria op='Equal' key='GSIS.GameKey' val='${gameKey}'/></criterias>`;
  const plays = call<TCPlay[] | null>("SearchForPlaysComplex", { criteria: Buffer.from(xml).toString("base64"), includeClips: "true" })
    .then((rows) => {
      const byPlay = new Map<number, TCPlay>();
      for (const p of rows ?? []) {
        const id = Number(p.PlayFieldValues?.["PFF.pff_GSISPLAYID"]);
        if (!Number.isFinite(id) || !p.Clips?.length) continue;
        // the same snap is indexed once per side of the ball; keep the copy with the most angles
        const prev = byPlay.get(id);
        if (!prev || (p.Clips?.length ?? 0) > (prev.Clips?.length ?? 0)) byPlay.set(id, p);
      }
      return byPlay;
    });
  games.set(gameKey, { at: Date.now(), plays });
  plays.catch(() => games.delete(gameKey));
  return plays;
}

function mediaUrl(mediaRef: string): Promise<string | null> {
  const hit = urls.get(mediaRef);
  if (hit && Date.now() - hit.at < URL_TTL) return hit.url;
  const url = call<string[] | null>("GetURLsForElement", { element: mediaRef }).then((u) => (u && u.length ? u[0] : null));
  urls.set(mediaRef, { at: Date.now(), url });
  url.catch(() => urls.delete(mediaRef));
  return url;
}

export async function filmForPlay(gameKey: number, playId: number): Promise<FilmPlay | null> {
  const play = (await gamePlays(gameKey)).get(playId);
  if (!play) return null;
  const viewName = new Map((play.ViewList ?? []).map((v) => [v.Id, v.Name]));
  const angles = await Promise.all((play.Clips ?? []).map(async (c) => {
    const view = viewName.get(c.ViewId) ?? "?";
    const url = await mediaUrl(c.MediaReferenceId);
    const fps = c.FPS || 59.94;
    return url ? { view, label: VIEW_LABEL[view] ?? view, url, start: c.MediaFrameStart / fps, end: c.MediaFrameEnd / fps } : null;
  }));
  const ok = angles.filter((a): a is FilmAngle => a !== null)
    .sort((a, b) => (VIEW_ORDER.indexOf(a.view) + 99) % 99 - (VIEW_ORDER.indexOf(b.view) + 99) % 99);
  return { gameKey, playId, title: play.Name.replace(/^\(Duplicate\)\s*/, ""), description: play.PlayFieldValues?.["GSIS.PlayDescription"] ?? null, angles: ok };
}
