"use client";

import Link from "next/link";
import { useRequireAuth } from "@/lib/auth-context";
import { Card } from "@/components/Card";
import type { Accent } from "@/components/Button";

const STEPS: {
  href: string;
  step: string;
  title: string;
  description: string;
  accent: Accent;
  iconBg: string;
  iconFg: string;
  icon: React.ReactNode;
}[] = [
  {
    href: "/doctors/new",
    step: "1",
    title: "Set up a doctor",
    description: "US-07: create a doctor profile with a weekly schedule.",
    accent: "violet",
    iconBg: "bg-violet-50 group-hover:bg-violet-700",
    iconFg: "text-violet-700 group-hover:text-white",
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
    step: "2",
    title: "Register a patient",
    description: "US-05: register a new patient and issue a UHID.",
    accent: "teal",
    iconBg: "bg-teal-50 group-hover:bg-teal-700",
    iconFg: "text-teal-700 group-hover:text-white",
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
    step: "3",
    title: "Book an OPD appointment",
    description: "US-08 / US-11: book a real-time slot and get an instant confirmation.",
    accent: "rose",
    iconBg: "bg-rose-50 group-hover:bg-rose-700",
    iconFg: "text-rose-700 group-hover:text-white",
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
      <h1 className="font-serif text-2xl font-semibold tracking-tight text-stone-900">
        Welcome, {session.username}
      </h1>
      <p className="mt-1 text-sm text-stone-500">
        The Sprint 1 workflow, in order: set up a doctor, register a patient, then book an appointment
        between them.
      </p>

      <div className="relative mt-10 grid gap-6 sm:grid-cols-3">
        <div
          aria-hidden
          className="pointer-events-none absolute left-0 right-0 top-5 hidden h-px bg-gradient-to-r from-violet-200 via-teal-200 to-rose-200 sm:block"
        />
        {STEPS.map((item) => (
          <Link key={item.href} href={item.href} className="group relative">
            <span className="absolute -top-3 left-5 z-10 flex h-6 w-6 items-center justify-center rounded-full border border-stone-200 bg-white text-xs font-semibold text-stone-500">
              {item.step}
            </span>
            <Card accent={item.accent} className="h-full pt-7 transition group-hover:-translate-y-0.5 group-hover:shadow-md">
              <span
                className={`flex h-9 w-9 items-center justify-center rounded-lg transition ${item.iconBg}`}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  className={`h-5 w-5 transition ${item.iconFg}`}
                >
                  {item.icon}
                </svg>
              </span>
              <h2 className="mt-3 font-serif font-semibold text-stone-900">{item.title}</h2>
              <p className="mt-1 text-sm text-stone-500">{item.description}</p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
