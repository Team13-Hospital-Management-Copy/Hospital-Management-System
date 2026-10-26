"use client";

import { useState, type FormEvent } from "react";
import { useRequireAuth } from "@/lib/auth-context";
import { ApiError, registerPatient, type PatientResponse } from "@/lib/api";
import { ErrorAlert, SuccessAlert } from "@/components/Alert";
import { Card } from "@/components/Card";
import { FormField } from "@/components/FormField";
import { PrimaryButton } from "@/components/Button";

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
      <h1 className="font-serif text-2xl font-semibold tracking-tight text-stone-900">Register a patient</h1>
      <p className="mt-1 text-sm text-stone-500">US-05: issues a unique hospital ID (UHID) on success.</p>

      {patient && (
        <div className="mt-6">
          <SuccessAlert>
            Registered <span className="font-semibold">{patient.full_name}</span> with UHID{" "}
            <span className="font-mono font-semibold">{patient.uhid}</span>. Use this UHID to book an
            appointment.
          </SuccessAlert>
        </div>
      )}

      <Card accent="teal" className="mt-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <FormField label="Full name" value={fullName} onChange={setFullName} required accent="teal" />
          <div className="grid grid-cols-2 gap-4">
            <FormField
              label="Age"
              type="number"
              value={age}
              onChange={setAge}
              required
              min={0}
              max={130}
              accent="teal"
            />
            <FormField label="Gender" value={gender} onChange={setGender} required accent="teal" />
          </div>
          <FormField label="Phone" value={phone} onChange={setPhone} required accent="teal" />
          <FormField label="Address" value={address} onChange={setAddress} accent="teal" />

          {error && <ErrorAlert message={error} />}

          <PrimaryButton type="submit" disabled={submitting} accent="teal">
            {submitting ? "Registering..." : "Register patient"}
          </PrimaryButton>
        </form>
      </Card>
    </div>
  );
}
