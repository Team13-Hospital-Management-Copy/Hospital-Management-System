"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { Card } from "@/components/Card";
import { FormField } from "@/components/FormField";
import { PrimaryButton } from "@/components/Button";
import { ErrorAlert } from "@/components/Alert";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="mb-1 text-2xl font-semibold text-slate-900">Staff login</h1>
      <p className="mb-6 text-sm text-slate-500">US-01: secure staff login with account lockout.</p>

      <Card>
        <form onSubmit={handleSubmit} className="space-y-4">
          <FormField label="Username" value={username} onChange={setUsername} required />
          <FormField label="Password" type="password" value={password} onChange={setPassword} required />

          {error && <ErrorAlert message={error} />}

          <PrimaryButton type="submit" disabled={submitting}>
            {submitting ? "Signing in..." : "Sign in"}
          </PrimaryButton>
        </form>
      </Card>

      <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
        <p className="font-medium text-slate-600">Demo accounts</p>
        <p className="mt-1">
          <code className="font-mono">admin1</code> / <code className="font-mono">Admin#12345</code>{" "}
          (Administrator)
        </p>
        <p>
          <code className="font-mono">reception1</code> / <code className="font-mono">Reception#12345</code>{" "}
          (Receptionist)
        </p>
        <p className="mt-1">
          Seed them with <code className="font-mono">python -m scripts.seed_demo_users</code> from{" "}
          <code className="font-mono">backend/</code>.
        </p>
      </div>
    </div>
  );
}
