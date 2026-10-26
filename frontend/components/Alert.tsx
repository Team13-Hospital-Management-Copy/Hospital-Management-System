import type { ReactNode } from "react";

export function ErrorAlert({ message }: { message: string }) {
  return (
    <p className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">{message}</p>
  );
}

export function SuccessAlert({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
      {children}
    </div>
  );
}
