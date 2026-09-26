/* eslint-disable @next/next/no-img-element */

/** Panthers wordmark aspect ratio (1280×696 source asset). */
const LOGO_W = 1280;
const LOGO_H = 696;

export function BrandLogo({ heightPx = 40 }: { heightPx?: number }) {
  const widthPx = Math.round((heightPx * LOGO_W) / LOGO_H);
  return (
    <span
      className="inline-block shrink-0 overflow-hidden"
      style={{ width: widthPx, height: heightPx }}
    >
      <img
        src="/panthers-logo.png"
        alt="Carolina Panthers"
        width={widthPx}
        height={heightPx}
        className="block h-full w-full max-w-none object-contain object-left"
        decoding="async"
      />
    </span>
  );
}
