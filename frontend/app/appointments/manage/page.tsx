"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRequireAuth } from "@/lib/auth-context";
import {
  cancelAppointment,
  getAppointment,
  getAppointmentNotifications,
  getAvailableSlots,
  rescheduleAppointment,
  type AppointmentOut,
  type NotificationOut,
} from "@/lib/api";
import { ErrorAlert, SuccessAlert } from "@/components/Alert";
import { Card } from "@/components/Card";
import { FormField } from "@/components/FormField";
import { PrimaryButton, SecondaryButton } from "@/components/Button";
import { EmptyState, PageHeader, StatusBadge, errorMessage, formatDateTime } from "@/components/Page";

export default function ManageAppointmentPage() {
  const session = useRequireAuth();
  const [lookupId, setLookupId] = useState("");
  const [appointment, setAppointment] = useState<AppointmentOut | null>(null);
  const [notifications, setNotifications] = useState<NotificationOut[]>([]);
  const [day, setDay] = useState("");
  const [slots, setSlots] = useState<string[]>([]);
  const [selectedSlot, setSelectedSlot] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setSelectedSlot("");
    if (!session || !appointment || !day) {
      setSlots([]);
      return;
    }
    getAvailableSlots(session.token, appointment.doctor_id, day)
      .then((result) => setSlots(result.available))
      .catch(() => setSlots([]));
  }, [session, appointment, day]);

  if (!session) return null;
  const token = session.token;

  async function load(id: number) {
    const [found, sent] = await Promise.all([getAppointment(token, id), getAppointmentNotifications(token, id)]);
    setAppointment(found);
    setNotifications(sent);
  }

  async function handleLookup(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setAppointment(null);
    try {
      await load(Number(lookupId));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function run(action: () => Promise<AppointmentOut>, message: string) {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await action();
      await load(updated.id);
      setNotice(message);
      setDay("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const active = appointment && appointment.status !== "CANCELLED";

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader
        title="Reschedule or cancel"
        description="US-10: find an appointment, then move it to another open slot or cancel it. The patient is notified (US-11)."
      />

      <Card accent="rose">
        <form onSubmit={handleLookup} className="flex items-end gap-3">
          <div className="flex-1">
            <FormField label="Appointment number" type="number" min={1} value={lookupId} onChange={setLookupId} required accent="rose" />
          </div>
          <PrimaryButton type="submit" accent="rose" className="w-auto">
            Find
          </PrimaryButton>
        </form>
      </Card>

      {error && <ErrorAlert message={error} />}
      {notice && <SuccessAlert>{notice}</SuccessAlert>}

      {appointment && (
        <Card className="space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-serif text-lg font-semibold">Appointment #{appointment.id}</p>
              <p className="mt-1 text-sm text-stone-500">
                Patient <span className="font-mono">{appointment.patient_uhid}</span> with doctor{" "}
                <span className="font-mono">{appointment.doctor_id}</span>
              </p>
              <p className="mt-1 text-sm text-stone-700">{formatDateTime(appointment.slot_start)}</p>
            </div>
            <div className="text-right">
              <StatusBadge status={appointment.status} />
              <p className="mt-2 text-xs text-stone-400">Rescheduled {appointment.rescheduled_count}×</p>
            </div>
          </div>

          {active && (
            <div className="space-y-3 border-t border-stone-100 pt-5">
              <p className="text-sm font-medium text-stone-700">Move to a new slot</p>
              <FormField label="Day" type="date" value={day} onChange={setDay} accent="rose" />
              {day && slots.length === 0 && <EmptyState>No open slots on this day.</EmptyState>}
              <div className="flex flex-wrap gap-2">
                {slots.map((slot) => (
                  <button
                    key={slot}
                    type="button"
                    onClick={() => setSelectedSlot(slot)}
                    className={`rounded-lg border px-3 py-1.5 text-sm transition ${
                      selectedSlot === slot
                        ? "border-rose-700 bg-rose-700 text-white"
                        : "border-stone-300 text-stone-700 hover:border-rose-300 hover:bg-rose-50"
                    }`}
                  >
                    {new Date(slot).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </button>
                ))}
              </div>
              <div className="flex gap-3">
                <PrimaryButton
                  type="button"
                  accent="rose"
                  disabled={busy || !selectedSlot}
                  onClick={() =>
                    run(() => rescheduleAppointment(token, appointment.id, selectedSlot), "Appointment rescheduled.")
                  }
                >
                  Reschedule
                </PrimaryButton>
                <SecondaryButton
                  type="button"
                  disabled={busy}
                  className="shrink-0 text-red-700"
                  onClick={() => {
                    if (window.confirm(`Cancel appointment #${appointment.id}?`))
                      run(() => cancelAppointment(token, appointment.id), "Appointment cancelled; the slot is free again.");
                  }}
                >
                  Cancel appointment
                </SecondaryButton>
              </div>
            </div>
          )}

          <div className="border-t border-stone-100 pt-5">
            <p className="text-sm font-medium text-stone-700">Notifications</p>
            {notifications.length === 0 && <EmptyState>None yet.</EmptyState>}
            <ul className="mt-2 divide-y divide-stone-100 text-sm text-stone-600">
              {notifications.map((n) => (
                <li key={n.id} className="flex items-center justify-between py-1.5">
                  <span>
                    {n.kind} via {n.channel}
                    <span className="ml-2 text-xs text-stone-400">{formatDateTime(n.scheduled_for)}</span>
                  </span>
                  <StatusBadge status={n.status} />
                </li>
              ))}
            </ul>
          </div>
        </Card>
      )}
    </div>
  );
}
