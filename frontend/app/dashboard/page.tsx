"use client";

import Link from "next/link";
import { useRequireAuth } from "@/lib/auth-context";

const ACTIONS = [
  {
    href: "/doctors/new",
    title: "Set up a doctor",
    description: "US-07: create a doctor profile with a weekly schedule.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 4.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Zm-6.5 15a6.5 6.5 0 0 1 13 0"
      />
    ),
  },
  {
    href: "/patients/new",
    title: "Register a patient",
    description: "US-05: register a new patient and issue a UHID.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
      />
    ),
  },
  {
    href: "/appointments/book",
    title: "Book an OPD appointment",
    description: "US-08 / US-11: book a real-time slot and get an instant confirmation.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6.75 3v2.25M17.25 3v2.25M3.75 8.25h16.5M4.5 6h15a.75.75 0 0 1 .75.75V19.5a.75.75 0 0 1-.75.75h-15a.75.75 0 0 1-.75-.75V6.75A.75.75 0 0 1 4.5 6Zm3 6.75h.008v.008H7.5V12.75Zm0 3h.008v.008H7.5v-3.008Zm4.5-3h.008v.008H12V12.75Zm0 3h.008v.008H12v-3.008Zm4.5-3h.008v.008H16.5V12.75Z"
      />
    ),
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
            className="group rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 transition group-hover:bg-indigo-600 group-hover:text-white">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-5 w-5">
                {action.icon}
              </svg>
            </span>
            <h2 className="mt-3 font-medium text-slate-900">{action.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{action.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
