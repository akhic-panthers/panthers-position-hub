import { cn } from "@/lib/utils";
import * as React from "react";

const variants = {
  primary: "bg-panthers-blue text-white hover:bg-panthers-bright",
  ghost: "bg-transparent text-foreground hover:bg-ink-800",
  outline: "border border-ink-700 bg-ink-850 text-foreground hover:bg-ink-800",
};

export const Button = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof variants }
>(({ className, variant = "primary", ...props }, ref) => (
  <button
    ref={ref}
    className={cn(
      "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50",
      variants[variant],
      className,
    )}
    {...props}
  />
));
Button.displayName = "Button";
