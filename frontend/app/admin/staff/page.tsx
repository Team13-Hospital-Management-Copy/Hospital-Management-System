"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useRequireAuth } from "@/lib/auth-context";
import { createStaff, listStaff, updateStaff, type StaffAccountOut } from "@/lib/api";
import { ErrorAlert, SuccessAlert } from "@/components/Alert";
import { Card } from "@/components/Card";
import { FormField, SelectField } from "@/components/FormField";
import { PrimaryButton, SecondaryButton } from "@/components/Button";
import { EmptyState, PageHeader, SectionTitle, StatusBadge, errorMessage, formatDateTime } from "@/components/Page";

// Mirrors backend app/roles.py.
const ROLES = ["DOCTOR", "RECEPTIONIST", "PHARMACIST", "ADMINISTRATOR", "SYSTEM_ADMINISTRATOR", "PATIENT"];
const roleOptions = ROLES.map((r) => ({ value: r, label: r.replace(/_/g, " ").toLowerCase() }));

export default function StaffPage() {
  const session = useRequireAuth();
  const [staff, setStaff] = useState<StaffAccountOut[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("DOCTOR");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!session) return;
    try {
      setStaff(await listStaff(session.token));
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [session]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (!session) return null;
  const token = session.token;

  async function attempt(action: () => Promise<unknown>, message: string) {
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(message);
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  function handleCreate(event: FormEvent) {
    event.preventDefault();
    attempt(() => createStaff(token, { username, password, role }), `Account ${username} created.`).then(() => {
      setUsername("");
      setPassword("");
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Staff accounts" description="US-19: create staff accounts, change their role, and deactivate them." />
      {error && <ErrorAlert message={error} />}
      {notice && <SuccessAlert>{notice}</SuccessAlert>}

      <div className="grid gap-6 lg:grid-cols-[20rem_1fr]">
        <Card accent="violet">
          <form onSubmit={handleCreate} className="space-y-4">
            <SectionTitle>New account</SectionTitle>
            <FormField label="Username" value={username} onChange={setUsername} required accent="violet" />
            <FormField label="Temporary password" type="password" value={password} onChange={setPassword} required accent="violet" />
            <SelectField label="Role" value={role} onChange={setRole} options={roleOptions} accent="violet" />
            <PrimaryButton type="submit" accent="violet">
              Create account
            </PrimaryButton>
          </form>
        </Card>

        <Card className="overflow-x-auto">
          <SectionTitle>All accounts</SectionTitle>
          {staff.length === 0 ? (
            <EmptyState>No accounts.</EmptyState>
          ) : (
            <table className="mt-3 w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-stone-400">
                <tr>
                  <th className="py-2 font-medium">User</th>
                  <th className="py-2 font-medium">Role</th>
                  <th className="py-2 font-medium">Status</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {staff.map((s) => {
                  const self = s.username === session.username;
                  return (
                    <tr key={s.id}>
                      <td className="py-2">
                        <span className="font-medium text-stone-900">{s.username}</span>
                        <span className="block text-xs text-stone-400">since {formatDateTime(s.created_at)}</span>
                      </td>
                      <td className="py-2">
                        <select
                          value={s.role}
                          disabled={self}
                          onChange={(e) =>
                            attempt(() => updateStaff(token, s.username, { role: e.target.value }), `${s.username} is now ${e.target.value}.`)
                          }
                          className="rounded-md border border-stone-300 bg-white px-2 py-1 text-xs disabled:opacity-50"
                        >
                          {roleOptions.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="space-x-1 py-2">
                        <StatusBadge status={s.is_active ? "ACTIVE" : "INACTIVE"} tone={s.is_active ? "green" : "grey"} />
                        {s.is_locked && <StatusBadge status="LOCKED" tone="red" />}
                      </td>
                      <td className="py-2 text-right">
                        {!self && (
                          <SecondaryButton
                            type="button"
                            onClick={() =>
                              attempt(
                                () => updateStaff(token, s.username, { is_active: !s.is_active }),
                                `${s.username} ${s.is_active ? "deactivated" : "reactivated"}.`
                              )
                            }
                          >
                            {s.is_active ? "Deactivate" : "Reactivate"}
                          </SecondaryButton>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}
