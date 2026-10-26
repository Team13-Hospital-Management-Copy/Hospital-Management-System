"use client";

import { useState, type FormEvent } from "react";
import { useRequireAuth } from "@/lib/auth-context";
import { ApiError, createDoctor, type DoctorOut, type ScheduleBlock } from "@/lib/api";
import { ErrorAlert, SuccessAlert } from "@/components/Alert";
import { Card } from "@/components/Card";
import { FormField } from "@/components/FormField";
import { PrimaryButton } from "@/components/Button";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function defaultBlock(): ScheduleBlock {
  return { weekday: 0, start_time: "09:00", end_time: "13:00" };
}

export default function CreateDoctorPage() {
  const session = useRequireAuth();
  const [fullName, setFullName] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [department, setDepartment] = useState("");
  const [slotMinutes, setSlotMinutes] = useState("30");
  const [schedule, setSchedule] = useState<ScheduleBlock[]>([defaultBlock()]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [doctor, setDoctor] = useState<DoctorOut | null>(null);

  if (!session) return null;

  function updateBlock(index: number, patch: Partial<ScheduleBlock>) {
    setSchedule((blocks) => blocks.map((block, i) => (i === index ? { ...block, ...patch } : block)));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setDoctor(null);
    setSubmitting(true);
    try {
      const created = await createDoctor(session!.token, {
        full_name: fullName,
        specialization,
        department,
        slot_minutes: Number(slotMinutes),
        schedule,
      });
      setDoctor(created);
      setFullName("");
      setSpecialization("");
      setDepartment("");
      setSchedule([defaultBlock()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="text-2xl font-semibold text-slate-900">Set up a doctor</h1>
      <p className="mt-1 text-sm text-slate-500">
        US-07: create a profile and weekly schedule (administrator only).
      </p>

      {doctor && (
        <div className="mt-6">
          <SuccessAlert>
            Created <span className="font-semibold">Dr. {doctor.full_name}</span> with doctor ID{" "}
            <span className="font-mono font-semibold">{doctor.doctor_id}</span>. Use this ID to book an
            appointment.
          </SuccessAlert>
        </div>
      )}

      <Card className="mt-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <FormField label="Full name" value={fullName} onChange={setFullName} required />
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Specialization" value={specialization} onChange={setSpecialization} required />
            <FormField label="Department" value={department} onChange={setDepartment} required />
          </div>
          <div className="w-32">
            <FormField
              label="Slot length (min)"
              type="number"
              value={slotMinutes}
              onChange={setSlotMinutes}
              required
              min={5}
              max={120}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">Weekly schedule</label>
            {schedule.map((block, index) => (
              <div key={index} className="mt-2 flex items-center gap-2">
                <select
                  value={block.weekday}
                  onChange={(e) => updateBlock(index, { weekday: Number(e.target.value) })}
                  className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm shadow-sm transition focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                >
                  {WEEKDAYS.map((day, i) => (
                    <option key={day} value={i}>
                      {day}
                    </option>
                  ))}
                </select>
                <input
                  type="time"
                  value={block.start_time}
                  onChange={(e) => updateBlock(index, { start_time: e.target.value })}
                  className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm shadow-sm transition focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
                <span className="text-slate-400">to</span>
                <input
                  type="time"
                  value={block.end_time}
                  onChange={(e) => updateBlock(index, { end_time: e.target.value })}
                  className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm shadow-sm transition focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </div>
            ))}
          </div>

          {error && <ErrorAlert message={error} />}

          <PrimaryButton type="submit" disabled={submitting}>
            {submitting ? "Creating..." : "Create doctor"}
          </PrimaryButton>
        </form>
      </Card>
    </div>
  );
}
