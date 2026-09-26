/* eslint-disable @next/next/no-img-element */
import { teamLogo } from "@/lib/constants";
import { normalizeTeamCode } from "@/lib/team-codes";
import { cn } from "@/lib/utils";

export function TeamLogo({
  team,
  size = 22,
  withCode = true,
  className,
}: {
  team: string | null | undefined;
  size?: number;
  withCode?: boolean;
  className?: string;
}) {
  const code = normalizeTeamCode(team);
  const src = teamLogo(code);
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      {src ? (
        <img src={src} alt={code ?? ""} width={size} height={size} className="object-contain" />
      ) : (
        <span className="inline-block rounded bg-ink-700" style={{ width: size, height: size }} />
      )}
      {withCode && <span className="font-semibold">{code ?? "—"}</span>}
    </span>
  );
}
