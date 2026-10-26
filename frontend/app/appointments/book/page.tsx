"use client";

import { useEffect, useState } from "react";
import { useRequireAuth } from "@/lib/auth-context";
import {
  ApiError,
  bookOpdAppointment,
  getAppointmentNotifications,
  getAvailableSlots,
  listDoctors,
  type AppointmentOut,
  type DoctorOut,
  type NotificationOut,
} from "@/lib/api";
import { ErrorAlert, SuccessAlert } from "@/components/Alert";

function tomorrow(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}

export default function BookAppointmentPage() {
  const session = useRequireAuth();

  const [doctors, setDoctors] = useState<DoctorOut[]>([]);
  const [patientUhid, setPatientUhid] = useState("");
  const [doctorId, setDoctorId] = useState("");
  const [day, setDay] = useState(tomorrow());
  const [slots, setSlots] = useState<string[]>([]);
  const [selectedSlot, setSelectedSlot] = useState("");
  const [loadingSlots, setLoadingSlots] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [appointment, setAppointment] = useState<AppointmentOut | null>(null);
  const [notifications, setNotifications] = useState<NotificationOut[]>([]);

  useEffect(() => {
    if (!session) return;
    listDoctors(session.token)
      .then((list) => {
        setDoctors(list);
        if (list.length > 0) setDoctorId((current) => current || list[0].doctor_id);
      })
      .catch(() => setError("Could not load doctors. Set one up first."));
  }, [session]);

  useEffect(() => {
    if (!session || !doctorId || !day) {
      setSlots([]);
      return;
    }
    setLoadingSlots(true);
    setSelectedSlot("");
    getAvailableSlots(session.token, doctorId, day)
      .then((result) => setSlots(result.available))
      .catch(() => setSlots([]))
      .finally(() => setLoadingSlots(false));
  }, [session, doctorId, day]);

  if (!session) return null;

  async function handleBook() {
    setError(null);
    setAppointment(null);
    setNotifications([]);
    setSubmitting(true);
    try {
      const created = await bookOpdAppointment(session!.token, {
        patient_uhid: patientUhid,
        doctor_id: doctorId,
        slot_start: selectedSlot,
      });
      setAppointment(created);
      const sent = await getAppointmentNotifications(session!.token, created.id);
      setNotifications(sent);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="text-2xl font-semibold text-slate-900">Book an OPD appointment</h1>
      <p className="mt-1 text-sm text-slate-500">
        US-08: pick an available slot. US-11: a confirmation is sent the moment it is booked.
      </p>

      {appointment && (
        <div className="mt-6 space-y-3">
          <SuccessAlert>
            Appointment <span className="font-mono font-semibold">#{appointment.id}</span> is{" "}
            <span className="font-semibold">{appointment.status}</span> for patient{" "}
            <span className="font-mono">{appointment.patient_uhid}</span> with doctor{" "}
            <span className="font-mono">{appointment.doctor_id}</span> at{" "}
            {new Date(appointment.slot_start).toLocaleString()}.
          </SuccessAlert>
          {notifications.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-medium text-slate-700">Notifications sent</h2>
              <ul className="mt-2 space-y-1 text-sm text-slate-600">
                {notifications.map((n) => (
                  <li key={n.id} className="flex items-center justify-between">
                    <span>
                      {n.kind} via {n.channel}
                    </span>
                    <span
                      className={
                        n.status === "SENT" ? "font-medium text-emerald-600" : "font-medium text-amber-600"
                      }
                    >
                      {n.status}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="mt-6 space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <label className="block text-sm font-medium text-slate-700">Patient UHID</label>
          <input
            required
            placeholder="HMS-000001"
            value={patientUhid}
            onChange={(e) => setPatientUhid(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono focus:border-slate-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Doctor</label>
          <select
            value={doctorId}
            onChange={(e) => setDoctorId(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          >
            {doctors.length === 0 && <option value="">No doctors yet - set one up first</option>}
            {doctors.map((d) => (
              <option key={d.doctor_id} value={d.doctor_id}>
                Dr. {d.full_name} ({d.doctor_id}) - {d.department}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Day</label>
          <input
            type="date"
            value={day}
            onChange={(e) => setDay(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Available slots</label>
          {loadingSlots && <p className="mt-2 text-sm text-slate-400">Loading...</p>}
          {!loadingSlots && slots.length === 0 && (
            <p className="mt-2 text-sm text-slate-400">No open slots on this day.</p>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            {slots.map((slot) => (
              <button
                key={slot}
                type="button"
                onClick={() => setSelectedSlot(slot)}
                className={`rounded-md border px-3 py-1.5 text-sm ${
                  selectedSlot === slot
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-300 text-slate-700 hover:bg-slate-50"
                }`}
              >
                {new Date(slot).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </button>
            ))}
          </div>
        </div>

        {error && <ErrorAlert message={error} />}

        <button
          type="button"
          disabled={submitting || !patientUhid || !doctorId || !selectedSlot}
          onClick={handleBook}
          className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {submitting ? "Booking..." : "Book appointment"}
        </button>
      </div>
    </div>
  );
}
