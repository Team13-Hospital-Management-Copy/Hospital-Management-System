import type { ReactNode } from "react";
import type { Accent } from "./Button";

const ACCENT_BORDER: Record<Accent, string> = {
  teal: "border-t-teal-600",
  violet: "border-t-violet-600",
  rose: "border-t-rose-600",
};

export function Card({
  children,
  className = "",
  accent,
}: {
  children: ReactNode;
  className?: string;
  accent?: Accent;
}) {
  return (
    <div
      className={`rounded-xl border border-stone-200 bg-white p-6 shadow-sm shadow-stone-900/5 ${
        accent ? `border-t-[3px] ${ACCENT_BORDER[accent]}` : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}
