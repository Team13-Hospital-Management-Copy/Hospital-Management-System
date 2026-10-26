"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export function Nav() {
  const { session, logout } = useAuth();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Link href={session ? "/dashboard" : "/"} className="text-lg font-semibold text-slate-900">
          Hospital Management System
        </Link>
        {session && (
          <div className="flex items-center gap-4 text-sm text-slate-600">
            <span>
              Signed in as <span className="font-medium text-slate-900">{session.username}</span>
            </span>
            <button
              onClick={() => logout()}
              className="rounded-md border border-slate-300 px-3 py-1.5 font-medium text-slate-700 hover:bg-slate-50"
            >
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
