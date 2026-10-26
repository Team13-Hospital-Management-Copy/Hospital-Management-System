import type { ButtonHTMLAttributes } from "react";

export type Accent = "teal" | "violet" | "rose";

const ACCENT_BUTTON: Record<Accent, string> = {
  teal: "bg-teal-700 hover:bg-teal-600 focus-visible:outline-teal-700",
  violet: "bg-violet-700 hover:bg-violet-600 focus-visible:outline-violet-700",
  rose: "bg-rose-700 hover:bg-rose-600 focus-visible:outline-rose-700",
};

interface PrimaryButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  accent?: Accent;
}

export function PrimaryButton({ className = "", accent = "teal", ...props }: PrimaryButtonProps) {
  return (
    <button
      {...props}
      className={`w-full rounded-lg px-4 py-2.5 text-sm font-medium text-white shadow-sm transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${ACCENT_BUTTON[accent]} ${className}`}
    />
  );
}
