"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export function Nav() {
  const { session, logout } = useAuth();

  return (
    <header className="sticky top-0 z-10 border-b border-stone-200 bg-stone-50/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Link href={session ? "/dashboard" : "/"} className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-teal-700 text-white">
            <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
              <path
                d="M3 12h4l2-6 4 12 2-6h6"
                stroke="currentColor"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <span className="font-serif text-lg font-semibold tracking-tight text-stone-900">
            Hospital Management System
          </span>
        </Link>
        {session && (
          <div className="flex items-center gap-4 text-sm text-stone-600">
            <span>
              Signed in as <span className="font-medium text-stone-900">{session.username}</span>
            </span>
            <button
              onClick={() => logout()}
              className="rounded-lg border border-stone-300 px-3 py-1.5 font-medium text-stone-700 transition hover:border-stone-400 hover:bg-white"
            >
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
