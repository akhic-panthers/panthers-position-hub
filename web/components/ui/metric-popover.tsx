"use client";

import { createPortal } from "react-dom";
import { useLayoutEffect, useState, type ReactNode, type RefObject } from "react";
import { cn } from "@/lib/utils";

const MAX_WIDTH_PX = 288;
const VIEWPORT_MARGIN = 8;

/** Fixed-position popover anchored to a header button; avoids table overflow clipping. */
export function MetricPopover({
  open,
  anchorRef,
  children,
  className,
}: {
  open: boolean;
  anchorRef: RefObject<HTMLElement | null>;
  children: ReactNode;
  className?: string;
}) {
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);

  useLayoutEffect(() => {
    if (!open || !anchorRef.current) {
      setPos(null);
      return;
    }
    const update = () => {
      const el = anchorRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const width = Math.min(MAX_WIDTH_PX, window.innerWidth - VIEWPORT_MARGIN * 2);
      let left = r.left;
      if (left + width > window.innerWidth - VIEWPORT_MARGIN) {
        left = window.innerWidth - VIEWPORT_MARGIN - width;
      }
      left = Math.max(VIEWPORT_MARGIN, left);
      setPos({ top: r.bottom + 6, left, width });
    };
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [open, anchorRef]);

  if (!open || !pos || typeof document === "undefined") return null;

  return createPortal(
    <div
      role="tooltip"
      className={cn(
        "fixed z-[200] rounded-md border border-ink-600 bg-ink-900 px-3 py-2.5 text-xs font-normal normal-case leading-relaxed tracking-normal text-foreground shadow-xl",
        "break-words [overflow-wrap:anywhere]",
        className,
      )}
      style={{ top: pos.top, left: pos.left, width: pos.width, maxWidth: pos.width }}
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
    >
      {children}
    </div>,
    document.body,
  );
}
