"use client";
/* eslint-disable @next/next/no-img-element */
// SIDE NAV — the Scout-Swarm shell adapted to this system: a fixed icon rail on the left,
// hover any icon and a flyout opens BESIDE the rail with that surface's name and its sub-tabs
// (deep links into the real ?mode / ?family / ?view states). The top bar is gone, so every
// dashboard gets the full viewport height; mobile keeps a slim top bar + slide-over drawer.
import { Suspense, useCallback, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import {
  BookOpen,
  Clapperboard,
  Menu,
  Shield,
  Users,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── The nav model: 6 surfaces, each with its real sub-tabs ─────────────────────
type SubLink = { href: string; label: string; note?: string; section?: string };
type Group = {
  key: string;
  label: string;
  tagline: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  /** path prefixes that light this group up */
  match: string[];
  sub: SubLink[];
};

const GROUPS: Group[] = [
  {
    key: "board", label: "Role Board", tagline: "What He Actually Plays", href: "/", icon: Users,
    match: ["/"],
    sub: [
      { href: "/?group=S", label: "Safeties", section: "Boards · Defense", note: "Post, half-field, box and slot, snap by snap." },
      { href: "/?group=CB", label: "Corners", section: "Boards · Defense", note: "Boundary vs nickel, and who travels." },
      { href: "/?group=LB", label: "Linebackers", section: "Boards · Defense" },
      { href: "/?group=EDGE", label: "Edge", section: "Boards · Defense" },
      { href: "/?group=IDL", label: "Interior Line", section: "Boards · Defense" },
      { href: "/?group=WR", label: "Receivers", section: "Boards · Offense", note: "Wide, slot, flexed, and who lines up over them." },
      { href: "/?group=TE", label: "Tight Ends", section: "Boards · Offense", note: "Inline, wing, flexed and split out." },
      { href: "/?group=RB", label: "Backs", section: "Boards · Offense" },
      { href: "/?team=CAR", label: "Panthers", section: "Our Room", note: "Every Carolina defender's role mix." },
    ],
  },
  {
    key: "player", label: "Player Room", tagline: "Field, Film, Blocks", href: "/player", icon: Clapperboard,
    match: ["/player"],
    sub: [
      { href: "/player", label: "Alignment Map", note: "Every snap where he stood, colored by the job." },
      { href: "/player?view=heat", label: "Heatmap", note: "Where he lives, and where his peers do." },
      { href: "/player?view=move", label: "First Two Seconds", note: "Where he went after the snap." },
      { href: "/player?view=blocks", label: "Block Map", note: "Who blocked him, and which gap he hit." },
    ],
  },
  {
    key: "teams", label: "Team Shells", tagline: "How They Deploy", href: "/teams", icon: Shield,
    match: ["/teams"],
    sub: [
      { href: "/teams", label: "Shell Mix", note: "One-high, two-high and zero, by down and distance." },
    ],
  },
];

const APPENDIX: Group = {
  key: "appendix", label: "Method", tagline: "Receipts & Gates", href: "/method", icon: BookOpen,
  match: ["/method"],
  sub: [
    { href: "/method", label: "Gates", note: "Every bar, written before the numbers." },
  ],
};

const ALL_GROUPS = [...GROUPS, APPENDIX];

// ── Active-state helpers ───────────────────────────────────────────────────────
function groupActive(g: Group, pathname: string) {
  return g.match.some((m) => pathname === m || pathname.startsWith(`${m}/`));
}
function subActive(s: SubLink, pathname: string, search: URLSearchParams) {
  const [path, query] = s.href.split("?");
  if (pathname !== path) return false;
  if (!query) return true;
  // every param in the link must match the live URL (side + pos, or to=office)
  const want = new URLSearchParams(query);
  for (const [k, v] of want) if (search.get(k) !== v) return false;
  return true;
}

// ── The flyout panel (opens beside the rail) ──────────────────────────────────
function Flyout({ g, pathname, search }: { g: Group; pathname: string; search: URLSearchParams }) {
  return (
    <div className="nav-flyout absolute left-full top-0 h-full w-80 border-r border-white/[0.07] bg-[#080b0f] shadow-[8px_0_32px_rgba(0,0,0,0.55)]">
      <div className="flex h-full flex-col overflow-y-auto px-3.5 py-5">
        <Link href={g.href} className="group mb-1.5 block rounded-lg px-3 py-2 hover:bg-white/[0.04]">
          <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-panthers-bright">{g.tagline}</div>
          <div className="mt-1 text-[22px] font-extrabold leading-tight tracking-tight text-white">{g.label}</div>
        </Link>
        <div className="mb-2 h-px bg-white/[0.07]" />
        <div className="space-y-0.5">
          {g.sub.map((s, i) => {
            const active = subActive(s, pathname, search);
            const newSection = s.section && s.section !== g.sub[i - 1]?.section;
            return (
              <div key={s.href}>
              {newSection && <div className="px-3 pb-1 pt-3.5 text-[11px] font-bold uppercase tracking-[0.16em] text-muted/70">{s.section}</div>}
              <Link
                href={s.href}
                className={cn(
                  "relative block rounded-lg px-3 py-2 transition-colors",
                  active ? "bg-panthers-blue/15" : "hover:bg-white/[0.04]",
                )}
              >
                <span
                  className={cn(
                    "absolute left-0 top-1/2 h-0 w-[3px] -translate-y-1/2 rounded-full bg-panthers-bright transition-all duration-200",
                    active && "h-6",
                  )}
                />
                <span className={cn("block text-[15px] font-semibold", active ? "text-panthers-bright" : "text-[#d4dbe1]")}>{s.label}</span>
                {s.note && <span className="mt-0.5 block text-[12px] leading-snug text-[#6b7684]">{s.note}</span>}
              </Link>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Rail icon ─────────────────────────────────────────────────────────────────
function RailIcon({ g, active, hovered, onEnter }: { g: Group; active: boolean; hovered: boolean; onEnter: () => void }) {
  const Icon = g.icon;
  return (
    <Link
      href={g.href}
      onMouseEnter={onEnter}
      onFocus={onEnter}
      aria-label={g.label}
      title={g.label}
      className={cn(
        "group relative flex h-11 w-11 items-center justify-center rounded-xl transition-all duration-200",
        active
          ? "bg-panthers-blue/20 text-panthers-bright"
          : hovered
            ? "bg-white/[0.06] text-white"
            : "text-[#6b7684] hover:text-white",
      )}
    >
      <span
        className={cn(
          "absolute -left-2.5 top-1/2 h-0 w-[3px] -translate-y-1/2 rounded-full bg-panthers-bright transition-all duration-300",
          active && "h-6",
        )}
      />
      <Icon className="size-[19px]" />
    </Link>
  );
}

// ── Desktop rail + flyout ─────────────────────────────────────────────────────
function DesktopRail() {
  const pathname = usePathname();
  const search = useSearchParams();
  const [open, setOpen] = useState<string | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const enter = useCallback((key: string) => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setOpen(key);
  }, []);
  const scheduleClose = useCallback(() => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setOpen(null), 140);
  }, []);
  const cancelClose = useCallback(() => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
  }, []);

  const openGroup = open ? ALL_GROUPS.find((g) => g.key === open) ?? null : null;
  // the assistant gets its own hover card. It has no sub-links, so a full 320px flyout would be
  // overkill — but a native title tooltip is slow, OS-styled and off-brand, and left the football
  // mark unexplained. FOCUS is wired alongside hover: keyboard users get it, and headless browsers
  // never deliver real hover events, so focus is also how it gets tested.

  return (
    <aside
      className="fixed inset-y-0 left-0 z-40 hidden w-16 lg:block"
      onMouseLeave={scheduleClose}
      onMouseEnter={cancelClose}
    >
      <div className="relative flex h-full flex-col items-center border-r border-white/[0.07] bg-[#05070a] py-3">
        {/* brand mark */}
        <Link href="/" aria-label="Home" title="Carolina Panthers Analytics" onMouseEnter={() => setOpen(null)}
          className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl transition-colors hover:bg-white/[0.06]">
          <img src="/panthers-logo.png" alt="Carolina Panthers Analytics" className="h-8 w-8 object-contain" draggable={false} />
        </Link>
        <div className="mb-2 h-px w-8 bg-white/[0.08]" />

        {/* the six surfaces */}
        <nav aria-label="Main navigation" className="flex flex-col items-center gap-1.5">
          {GROUPS.map((g) => (
            <RailIcon key={g.key} g={g} active={groupActive(g, pathname)} hovered={open === g.key} onEnter={() => enter(g.key)} />
          ))}
        </nav>

        <div className="my-2 h-px w-8 bg-white/[0.08]" />
        <RailIcon g={APPENDIX} active={groupActive(APPENDIX, pathname)} hovered={open === APPENDIX.key} onEnter={() => enter(APPENDIX.key)} />

        {/* the assistant, pinned to the bottom */}
        <div className="mt-auto flex flex-col items-center gap-2 pb-1">
          <img src="/nfl-logo.png" alt="NFL" className="h-5 w-auto opacity-40" draggable={false} />
        </div>

        {/* the flyout — beside the rail, full height */}
        {openGroup && <Flyout g={openGroup} pathname={pathname} search={search} />}
      </div>
    </aside>
  );
}

// ── Mobile: slim top bar + slide-over drawer with the full tree ───────────────
function MobileNav() {
  const pathname = usePathname();
  const search = useSearchParams();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <>
      <div className="sticky top-0 z-40 flex items-center justify-between border-b border-white/[0.07] bg-[#05070a]/95 px-3 py-2 backdrop-blur lg:hidden">
        <Link href="/" className="flex items-center gap-2">
          <img src="/panthers-logo.png" alt="" className="h-7 w-7 object-contain" draggable={false} />
          <span className="text-sm font-extrabold tracking-tight text-white">
            PANTHERS <span className="text-panthers-bright">ANALYTICS</span>
          </span>
        </Link>
        <button type="button" onClick={() => setOpen(true)} aria-label="Open navigation"
          className="rounded-lg border border-white/10 p-2 text-[#c9d2d9]">
          <Menu className="size-5" />
        </button>
      </div>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <button type="button" aria-label="Close navigation" className="absolute inset-0 bg-black/60" onClick={close} />
          <aside className="absolute inset-y-0 left-0 flex w-80 flex-col overflow-y-auto border-r border-white/[0.07] bg-[#05070a] px-3 py-4">
            <div className="mb-2 flex items-center justify-between px-2">
              <span className="text-sm font-extrabold tracking-tight text-white">
                PANTHERS <span className="text-panthers-bright">ANALYTICS</span>
              </span>
              <button type="button" onClick={close} aria-label="Close" className="rounded-lg p-1.5 text-[#c9d2d9]">
                <X className="size-5" />
              </button>
            </div>
            {[...GROUPS, APPENDIX].map((g) => (
              <div key={g.key} className="mb-1.5">
                <Link href={g.href} onClick={close}
                  className={cn("block rounded-lg px-3 py-2 text-[17px] font-extrabold tracking-tight",
                    groupActive(g, pathname) ? "text-panthers-bright" : "text-white")}>
                  {g.label}
                </Link>
                <div className="space-y-0.5 pl-2">
                  {g.sub.map((s) => (
                    <Link key={s.href} href={s.href} onClick={close}
                      className={cn("block rounded-lg px-3 py-1.5 text-[14.5px] font-semibold",
                        subActive(s, pathname, search) ? "bg-panthers-blue/15 text-panthers-bright" : "text-[#8b949e] hover:text-white")}>
                      {s.label}
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </aside>
        </div>
      )}
    </>
  );
}

function SideNavInner() {
  return (
    <>
      <DesktopRail />
      <MobileNav />
    </>
  );
}

/** The app shell nav. useSearchParams needs a Suspense boundary when rendered from the root layout. */
export function SideNav() {
  return (
    <Suspense fallback={null}>
      <SideNavInner />
    </Suspense>
  );
}
