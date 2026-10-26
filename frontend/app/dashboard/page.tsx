"use client";

import Link from "next/link";
import { useRequireAuth } from "@/lib/auth-context";

const ACTIONS = [
  {
    href: "/doctors/new",
    title: "Set up a doctor",
    description: "US-07: create a doctor profile with a weekly schedule.",
  },
  {
    href: "/patients/new",
    title: "Register a patient",
    description: "US-05: register a new patient and issue a UHID.",
  },
  {
    href: "/appointments/book",
    title: "Book an OPD appointment",
    description: "US-08 / US-11: book a real-time slot and get an instant confirmation.",
  },
];

export default function DashboardPage() {
  const session = useRequireAuth();
  if (!session) return null;

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Welcome, {session.username}</h1>
      <p className="mt-1 text-sm text-slate-500">
        Sprint 1 workflow: set up a doctor, register a patient, then book an appointment between them.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {ACTIONS.map((action) => (
          <Link
            key={action.href}
            href={action.href}
            className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition hover:border-slate-400 hover:shadow"
          >
            <h2 className="font-medium text-slate-900">{action.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{action.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
