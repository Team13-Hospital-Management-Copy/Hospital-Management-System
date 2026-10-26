"use client";

import { useState, type FormEvent } from "react";
import { useRequireAuth } from "@/lib/auth-context";
import { ApiError, registerPatient, type PatientResponse } from "@/lib/api";
import { ErrorAlert, SuccessAlert } from "@/components/Alert";

export default function RegisterPatientPage() {
  const session = useRequireAuth();
  const [fullName, setFullName] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [patient, setPatient] = useState<PatientResponse | null>(null);

  if (!session) return null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setPatient(null);
    setSubmitting(true);
    try {
      const created = await registerPatient(session!.token, {
        full_name: fullName,
        age: Number(age),
        gender,
        phone,
        address,
      });
      setPatient(created);
      setFullName("");
      setAge("");
      setGender("");
      setPhone("");
      setAddress("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="text-2xl font-semibold text-slate-900">Register a patient</h1>
      <p className="mt-1 text-sm text-slate-500">US-05: issues a unique hospital ID (UHID) on success.</p>

      {patient && (
        <div className="mt-6">
          <SuccessAlert>
            Registered <span className="font-semibold">{patient.full_name}</span> with UHID{" "}
            <span className="font-mono font-semibold">{patient.uhid}</span>. Use this UHID to book an
            appointment.
          </SuccessAlert>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-6 space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <Field label="Full name" value={fullName} onChange={setFullName} required />
        <div className="grid grid-cols-2 gap-4">
          <Field label="Age" type="number" value={age} onChange={setAge} required min={0} max={130} />
          <Field label="Gender" value={gender} onChange={setGender} required />
        </div>
        <Field label="Phone" value={phone} onChange={setPhone} required />
        <Field label="Address" value={address} onChange={setAddress} />

        {error && <ErrorAlert message={error} />}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {submitting ? "Registering..." : "Register patient"}
        </button>
      </form>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required = false,
  min,
  max,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
  min?: number;
  max?: number;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700">{label}</label>
      <input
        type={type}
        required={required}
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
      />
    </div>
  );
}
