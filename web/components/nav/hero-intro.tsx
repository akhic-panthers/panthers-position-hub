// HERO INTRO — the gradient/glow front-door card each lab opens with. One component so the
// Prediction Simulator, Play Simulator, Matchup Lab and Scheme Lab all read as one system:
// an eyebrow, a big two-tone headline, a measured line, and a row of tracked-caps chips.
export function HeroIntro({
  eyebrow, lead, accent, sub, chips,
}: {
  eyebrow: string;
  lead: string;
  accent: string;
  sub: string;
  chips: string[];
}) {
  return (
    <div className="glow-blue relative mb-5 overflow-hidden rounded-2xl border border-panthers-bright/25 bg-gradient-to-br from-panthers-blue/15 via-ink-900 to-ink-900 px-5 py-6 sm:px-7">
      <div className="eyebrow text-panthers-bright">{eyebrow}</div>
      {/* no width cap — the headline uses the full card width, so it sits on one line when the
          viewport has room (full screen) and wraps naturally only when the window is narrow */}
      <h1 className="mt-1.5 text-[26px] font-extrabold leading-[1.08] tracking-tight text-white sm:text-[34px]">
        {lead} <span className="text-panthers-bright">{accent}</span>
      </h1>
      <p className="mt-2.5 max-w-2xl text-[13.5px] leading-relaxed text-[#aab5bf]">{sub}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {chips.map((c) => (
          <span key={c} className="rounded-full border border-white/12 bg-white/[0.04] px-3 py-1 text-[10.5px] font-bold uppercase tracking-[0.12em] text-white/80">{c}</span>
        ))}
      </div>
    </div>
  );
}
