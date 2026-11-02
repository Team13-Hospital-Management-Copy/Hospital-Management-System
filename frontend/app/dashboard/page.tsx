"use client";

import Link from "next/link";
import { useRequireAuth } from "@/lib/auth-context";
import { Card } from "@/components/Card";
import type { Accent } from "@/components/Button";

interface Tile {
  href: string;
  title: string;
  description: string;
  icon: string; // SVG path, 24x24 outline
}

// The UI shows every area to everyone; the backend's RBAC (US-04) decides what each role can actually do.
const GROUPS: { role: string; accent: Accent; iconBg: string; iconFg: string; tiles: Tile[] }[] = [
  {
    role: "Front desk",
    accent: "rose",
    iconBg: "bg-rose-50 group-hover:bg-rose-700",
    iconFg: "text-rose-700 group-hover:text-white",
    tiles: [
      {
        href: "/patients/new",
        title: "Register a patient",
        description: "US-05: issue a UHID.",
        icon: "M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
      },
      {
        href: "/appointments/book",
        title: "Book an appointment",
        description: "US-08 / US-11: real-time slots, instant confirmation.",
        icon: "M6.75 3v2.25M17.25 3v2.25M3.75 8.25h16.5M4.5 6h15a.75.75 0 0 1 .75.75V19.5a.75.75 0 0 1-.75.75h-15a.75.75 0 0 1-.75-.75V6.75A.75.75 0 0 1 4.5 6Z",
      },
      {
        href: "/appointments/manage",
        title: "Reschedule or cancel",
        description: "US-09 / US-10: move or cancel without double-booking.",
        icon: "M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182",
      },
      {
        href: "/billing",
        title: "Billing",
        description: "US-17: consolidated bill, discounts, payments, receipts.",
        icon: "M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5A2.25 2.25 0 0 0 4.5 19.5Z",
      },
      {
        href: "/inpatient",
        title: "Admission & discharge",
        description: "US-16: beds, admit, discharge summary.",
        icon: "M2.25 12l8.954-8.955a1.126 1.126 0 0 1 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75",
      },
    ],
  },
  {
    role: "Clinical",
    accent: "violet",
    iconBg: "bg-violet-50 group-hover:bg-violet-700",
    iconFg: "text-violet-700 group-hover:text-white",
    tiles: [
      {
        href: "/clinical",
        title: "Doctor's workspace",
        description: "US-12 to US-15: consultation, prescription, lab tests, patient record.",
        icon: "M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08M15.75 18H18M8.25 8.25V6.108c0-1.135.845-2.098 1.976-2.192.373-.03.748-.057 1.123-.08M8.25 8.25H5.625c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25Z",
      },
      {
        href: "/pharmacy",
        title: "Pharmacy",
        description: "Dispense against prescriptions; low-stock and expiry alerts.",
        icon: "M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23-.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5",
      },
    ],
  },
  {
    role: "Administration",
    accent: "teal",
    iconBg: "bg-teal-50 group-hover:bg-teal-700",
    iconFg: "text-teal-700 group-hover:text-white",
    tiles: [
      {
        href: "/doctors/new",
        title: "Set up a doctor",
        description: "US-07: profile and weekly schedule.",
        icon: "M12 4.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Zm-6.5 15a6.5 6.5 0 0 1 13 0",
      },
      {
        href: "/admin/staff",
        title: "Staff accounts",
        description: "US-19: create, change role, deactivate.",
        icon: "M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z",
      },
      {
        href: "/billing",
        title: "Prices & discount schemes",
        description: "US-17: the tariff and schemes billing uses.",
        icon: "M9.568 3H5.25A2.25 2.25 0 0 0 3 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 0 0 5.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 0 0 9.568 3Z",
      },
      {
        href: "/admin/reports",
        title: "Reports",
        description: "US-20: footfall, revenue, occupancy; PDF/CSV.",
        icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z",
      },
    ],
  },
];

export default function DashboardPage() {
  const session = useRequireAuth();
  if (!session) return null;

  return (
    <div className="space-y-10">
      <div>
        <h1 className="font-serif text-2xl font-semibold tracking-tight text-stone-900">Welcome, {session.username}</h1>
        <p className="mt-1 text-sm text-stone-500">
          Pick an area. You&apos;ll only be able to act where your role allows it; anything else is refused by the server.
        </p>
      </div>

      {GROUPS.map((group) => (
        <section key={group.role}>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-400">{group.role}</h2>
          <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {group.tiles.map((tile) => (
              <Link key={tile.title} href={tile.href} className="group">
                <Card accent={group.accent} className="h-full transition group-hover:-translate-y-0.5 group-hover:shadow-md">
                  <span className={`flex h-9 w-9 items-center justify-center rounded-lg transition ${group.iconBg}`}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className={`h-5 w-5 transition ${group.iconFg}`}>
                      <path strokeLinecap="round" strokeLinejoin="round" d={tile.icon} />
                    </svg>
                  </span>
                  <h3 className="mt-3 font-serif font-semibold text-stone-900">{tile.title}</h3>
                  <p className="mt-1 text-sm text-stone-500">{tile.description}</p>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
