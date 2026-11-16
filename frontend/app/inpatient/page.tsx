"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useRequireAuth } from "@/lib/auth-context";
import {
  addBed,
  admitPatient,
  dischargePatient,
  fetchAuthorizedFile,
  listBeds,
  type AdmissionOut,
  type BedOut,
  type DischargeSummary,
} from "@/lib/api";
import { ErrorAlert, SuccessAlert } from "@/components/Alert";
import { Card } from "@/components/Card";
import { FormField, SelectField, TextAreaField } from "@/components/FormField";
import { PrimaryButton, SecondaryButton } from "@/components/Button";
import { EmptyState, PageHeader, SectionTitle, errorMessage, formatDateTime } from "@/components/Page";

export default function InpatientPage() {
  const session = useRequireAuth();
  const [beds, setBeds] = useState<BedOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!session) return;
    try {
      setBeds(await listBeds(session.token));
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [session]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (!session) return null;

  const wards = [...new Set(beds.map((b) => b.ward))].sort();
  const free = beds.filter((b) => b.is_active && !b.occupied);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Admission & discharge"
        description="US-16: admit a patient to a free bed, then discharge them and print the summary. The bed is released automatically."
      />
      {error && <ErrorAlert message={error} />}

      <Card>
        <div className="flex items-baseline justify-between">
          <SectionTitle>Beds</SectionTitle>
          <p className="text-sm text-stone-500">
            {free.length} of {beds.filter((b) => b.is_active).length} free
          </p>
        </div>
        {beds.length === 0 && <EmptyState>No beds yet. Add one below.</EmptyState>}
        <div className="mt-3 space-y-4">
          {wards.map((ward) => (
            <div key={ward}>
              <p className="text-xs font-medium uppercase tracking-wide text-stone-400">{ward}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {beds
                  .filter((b) => b.ward === ward)
                  .map((b) => (
                    <span
                      key={b.id}
                      title={b.occupied ? "Occupied" : b.is_active ? "Free" : "Inactive"}
                      className={`rounded-lg border px-3 py-2 font-mono text-sm ${
                        !b.is_active
                          ? "border-stone-200 bg-stone-100 text-stone-400 line-through"
                          : b.occupied
                            ? "border-rose-200 bg-rose-50 text-rose-800"
                            : "border-teal-200 bg-teal-50 text-teal-800"
                      }`}
                    >
                      {b.bed_number}
                    </span>
                  ))}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 flex gap-4 text-xs text-stone-500">
          <Legend className="border-teal-200 bg-teal-50" label="Free" />
          <Legend className="border-rose-200 bg-rose-50" label="Occupied" />
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <AdmitPanel token={session.token} freeBeds={free} onAdmitted={refresh} />
        <div className="space-y-6">
          <DischargePanel token={session.token} onDischarged={refresh} />
          <AddBedPanel token={session.token} onAdded={refresh} />
        </div>
      </div>
    </div>
  );
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-3 w-3 rounded border ${className}`} />
      {label}
    </span>
  );
}

function AdmitPanel({ token, freeBeds, onAdmitted }: { token: string; freeBeds: BedOut[]; onAdmitted: () => void }) {
  const [uhid, setUhid] = useState("");
  const [bedId, setBedId] = useState("");
  const [diagnosis, setDiagnosis] = useState("");
  const [treatment, setTreatment] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [admitted, setAdmitted] = useState<AdmissionOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedBed = bedId || String(freeBeds[0]?.id ?? "");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setAdmitted(null);
    try {
      const admission = await admitPatient(token, {
        patient_uhid: uhid,
        bed_id: Number(selectedBed),
        diagnosis,
        treatment,
        follow_up_instructions: followUp,
      });
      setAdmitted(admission);
      setUhid("");
      setBedId("");
      setDiagnosis("");
      setTreatment("");
      setFollowUp("");
      onAdmitted();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card accent="teal">
      <form onSubmit={handleSubmit} className="space-y-4">
        <SectionTitle>Admit a patient</SectionTitle>
        <FormField label="Patient UHID" value={uhid} onChange={setUhid} required mono />
        <SelectField
          label="Bed"
          value={selectedBed}
          onChange={setBedId}
          options={
            freeBeds.length
              ? freeBeds.map((b) => ({ value: String(b.id), label: `${b.bed_number} · ${b.ward}` }))
              : [{ value: "", label: "No free beds" }]
          }
        />
        <FormField label="Diagnosis" value={diagnosis} onChange={setDiagnosis} />
        <TextAreaField label="Treatment" value={treatment} onChange={setTreatment} rows={2} />
        <TextAreaField label="Follow-up instructions" value={followUp} onChange={setFollowUp} rows={2} />
        {error && <ErrorAlert message={error} />}
        {admitted && (
          <SuccessAlert>
            Admitted as <span className="font-mono font-semibold">admission #{admitted.id}</span>. Keep this number for
            discharge and billing.
          </SuccessAlert>
        )}
        <PrimaryButton type="submit" disabled={!uhid || !selectedBed}>
          Admit
        </PrimaryButton>
      </form>
    </Card>
  );
}

function DischargePanel({ token, onDischarged }: { token: string; onDischarged: () => void }) {
  const [admissionId, setAdmissionId] = useState("");
  const [summary, setSummary] = useState<DischargeSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSummary(null);
    if (!window.confirm(`Discharge admission #${admissionId}? This frees the bed.`)) return;
    try {
      setSummary(await dischargePatient(token, Number(admissionId)));
      onDischarged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function handlePrint() {
    if (!summary) return;
    try {
      const blob = await fetchAuthorizedFile(token, `/inpatient/admissions/${summary.admission_id}/discharge-summary/print`);
      window.open(URL.createObjectURL(blob), "_blank");
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card className="space-y-4">
      <SectionTitle>Discharge</SectionTitle>
      <form onSubmit={handleSubmit} className="flex items-end gap-3">
        <div className="flex-1">
          <FormField label="Admission number" type="number" min={1} value={admissionId} onChange={setAdmissionId} required />
        </div>
        <PrimaryButton type="submit" className="w-auto">
          Discharge
        </PrimaryButton>
      </form>
      {error && <ErrorAlert message={error} />}
      {summary && (
        <div className="space-y-2 rounded-lg border border-stone-200 bg-stone-50 p-4 text-sm">
          <p className="font-medium text-stone-900">
            {summary.patient_name} <span className="font-mono text-xs text-stone-500">{summary.patient_uhid}</span>
          </p>
          <p className="text-stone-600">
            {summary.bed_number} · {summary.ward} · {formatDateTime(summary.admitted_at)} → {formatDateTime(summary.discharged_at)}
          </p>
          {summary.diagnosis && <p><span className="text-stone-400">Diagnosis:</span> {summary.diagnosis}</p>}
          {summary.treatment && <p><span className="text-stone-400">Treatment:</span> {summary.treatment}</p>}
          {summary.follow_up_instructions && (
            <p><span className="text-stone-400">Follow-up:</span> {summary.follow_up_instructions}</p>
          )}
          <SecondaryButton type="button" onClick={handlePrint}>
            Print summary
          </SecondaryButton>
        </div>
      )}
    </Card>
  );
}

function AddBedPanel({ token, onAdded }: { token: string; onAdded: () => void }) {
  const [bedNumber, setBedNumber] = useState("");
  const [ward, setWard] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    try {
      const bed = await addBed(token, { bed_number: bedNumber, ward });
      setNotice(`Bed ${bed.bed_number} added to ${bed.ward}.`);
      setBedNumber("");
      onAdded();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card className="space-y-4">
      <SectionTitle>Add a bed</SectionTitle>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Bed number" placeholder="G-101" value={bedNumber} onChange={setBedNumber} required mono />
          <FormField label="Ward" placeholder="General" value={ward} onChange={setWard} required />
        </div>
        {error && <ErrorAlert message={error} />}
        {notice && <SuccessAlert>{notice}</SuccessAlert>}
        <PrimaryButton type="submit">Add bed</PrimaryButton>
      </form>
    </Card>
  );
}
