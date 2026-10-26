"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import * as api from "./api";

interface Session {
  token: string;
  username: string;
}

interface AuthContextValue {
  session: Session | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const STORAGE_KEY = "hms-demo-session";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) setSession(JSON.parse(raw));
    } catch {
      // ignore corrupt/unavailable storage
    }
    setReady(true);
  }, []);

  async function login(username: string, password: string) {
    const result = await api.login(username, password);
    if (!result.token) throw new Error("Login succeeded but no token was returned.");
    const next = { token: result.token, username };
    setSession(next);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  async function logout() {
    if (session) {
      try {
        await api.logout(session.token);
      } catch {
        // session may already be expired server-side; clear locally regardless
      }
    }
    setSession(null);
    window.localStorage.removeItem(STORAGE_KEY);
  }

  return <AuthContext.Provider value={{ session, ready, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/** Redirects to /login if there is no session once the stored session has been read. */
export function useRequireAuth(): Session | null {
  const { session, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  return session;
}
