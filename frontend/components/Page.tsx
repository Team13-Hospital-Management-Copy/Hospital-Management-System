import type { ReactNode } from "react";

export function PageHeader({ title, description }: { title: string; description: ReactNode }) {
  return (
    <div>
      <h1 className="font-serif text-2xl font-semibold tracking-tight text-stone-900">{title}</h1>
      <p className="mt-1 text-sm text-stone-500">{description}</p>
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="font-serif text-lg font-semibold text-stone-900">{children}</h2>;
}

const BADGE_TONE: Record<string, string> = {
  green: "bg-teal-50 text-teal-700",
  amber: "bg-amber-50 text-amber-700",
  red: "bg-red-50 text-red-700",
  grey: "bg-stone-100 text-stone-600",
  violet: "bg-violet-50 text-violet-700",
};

/** Maps the backend's status strings onto a colour so every page shows them the same way. */
const STATUS_TONE: Record<string, keyof typeof BADGE_TONE> = {
  BOOKED: "green",
  RESCHEDULED: "violet",
  CANCELLED: "red",
  ORDERED: "amber",
  COMPLETED: "green",
  OPEN: "amber",
  PARTIALLY_PAID: "violet",
  PAID: "green",
  SENT: "green",
  PENDING: "amber",
};

export function StatusBadge({ status, tone }: { status: string; tone?: keyof typeof BADGE_TONE }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${BADGE_TONE[tone ?? STATUS_TONE[status] ?? "grey"]}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: T; label: string }[];
  active: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1 rounded-xl border border-stone-200 bg-white p-1 shadow-sm">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
            active === tab.id ? "bg-stone-900 text-white" : "text-stone-600 hover:bg-stone-100"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="text-sm text-stone-400">{children}</p>;
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Could not reach the server.";
}

export function formatDateTime(value: string): string {
  return new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

export function rupees(value: string | number): string {
  return `₹${Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
