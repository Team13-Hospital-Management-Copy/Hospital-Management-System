import type { ReactNode } from "react";

export function ErrorAlert({ message }: { message: string }) {
  return (
    <p className="flex items-start gap-2 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">
      <svg viewBox="0 0 24 24" fill="none" className="mt-0.5 h-4 w-4 shrink-0">
        <path
          d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a1 1 0 0 0 .86 1.5h18.64a1 1 0 0 0 .86-1.5L13.71 3.86a1 1 0 0 0-1.72 0Z"
          stroke="currentColor"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span>{message}</span>
    </p>
  );
}

export function SuccessAlert({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-teal-100 bg-teal-50 px-4 py-3 text-sm text-teal-900">
      <svg viewBox="0 0 24 24" fill="none" className="mt-0.5 h-4 w-4 shrink-0">
        <path
          d="m4.5 12.75 6 6 9-13.5"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span>{children}</span>
    </div>
  );
}
