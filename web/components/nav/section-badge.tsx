import { SECTION_ACCENT, type Section } from "@/lib/constants";

export function SectionBadge({ section, label }: { section: Section; label: string }) {
  const color = SECTION_ACCENT[section];
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider"
      style={{ color, backgroundColor: `${color}1a`, border: `1px solid ${color}44` }}
    >
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

/** Page header — the one voice every surface opens with: a tracked-caps eyebrow in the
 *  section accent, a display title, a measured subtitle, and a hairline that hands off
 *  to the dashboard. Same API as before, so every page upgrades at once. */
export function PageHeader({
  section,
  badge,
  title,
  subtitle,
  subtitleClassName = "max-w-2xl",
}: {
  section: Section;
  badge: string;
  title: string;
  subtitle?: string;
  /** width constraint for the subtitle; pass e.g. "max-w-4xl" to keep a long subtitle on one line */
  subtitleClassName?: string;
}) {
  const color = SECTION_ACCENT[section];
  return (
    <header className="mb-6">
      <div className="flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
        <span className="eyebrow" style={{ color }}>{badge}</span>
      </div>
      <h1 className="mt-1.5 text-[26px] font-extrabold leading-tight tracking-tight text-white sm:text-3xl">
        {title}
      </h1>
      {subtitle && (
        <p className={`mt-1.5 text-[13px] leading-relaxed text-muted ${subtitleClassName}`}>{subtitle}</p>
      )}
      <div className="mt-4 flex items-center">
        <span className="h-px w-16 shrink-0" style={{ backgroundColor: `${color}88` }} />
        <span className="h-px flex-1 bg-gradient-to-r from-white/10 to-transparent" />
      </div>
    </header>
  );
}
