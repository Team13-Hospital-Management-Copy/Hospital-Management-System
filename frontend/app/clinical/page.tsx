"use client";

import { useState, type FormEvent } from "react";
import { useRequireAuth } from "@/lib/auth-context";
import {
  createConsultation,
  createPrescription,
  getPatientEhr,
  listLabTests,
  orderLabTest,
  recordLabResult,
  type ConsultationOut,
  type EHRVisit,
  type LabTestOut,
  type PatientResponse,
  type PrescriptionOut,
} from "@/lib/api";
import { ErrorAlert, SuccessAlert } from "@/components/Alert";
import { Card } from "@/components/Card";
import { FormField, TextAreaField } from "@/components/FormField";
import { PrimaryButton, SecondaryButton } from "@/components/Button";
import { EmptyState, PageHeader, StatusBadge, Tabs, errorMessage, formatDateTime } from "@/components/Page";

type Tab = "consultation" | "prescription" | "lab" | "record";

const TABS: { id: Tab; label: string }[] = [
  { id: "consultation", label: "Consultation" },
  { id: "prescription", label: "Prescription" },
  { id: "lab", label: "Lab tests" },
  { id: "record", label: "Patient record" },
];

export default function ClinicalPage() {
  const session = useRequireAuth();
  const [tab, setTab] = useState<Tab>("consultation");
  // Carried between tabs so a doctor can go consultation -> prescription -> lab without retyping.
  const [lastConsultation, setLastConsultation] = useState<ConsultationOut | null>(null);

  if (!session) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Doctor's workspace"
        description="Record the visit (US-12), prescribe (US-13), order and record lab tests (US-14) and read the patient's full history (US-15)."
      />
      <Tabs tabs={TABS} active={tab} onChange={setTab} />
      {tab === "consultation" && <ConsultationForm token={session.token} onSaved={setLastConsultation} />}
      {tab === "prescription" && <PrescriptionForm token={session.token} consultation={lastConsultation} />}
      {tab === "lab" && <LabTests token={session.token} consultation={lastConsultation} />}
      {tab === "record" && <PatientRecord token={session.token} initialUhid={lastConsultation?.patient_uhid ?? ""} />}
    </div>
  );
}

function optionalNumber(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

function ConsultationForm({ token, onSaved }: { token: string; onSaved: (c: ConsultationOut) => void }) {
  const [appointmentId, setAppointmentId] = useState("");
  const [diagnosis, setDiagnosis] = useState("");
  const [bloodPressure, setBloodPressure] = useState("");
  const [temperature, setTemperature] = useState("");
  const [pulse, setPulse] = useState("");
  const [spo2, setSpo2] = useState("");
  const [notes, setNotes] = useState("");
  const [saved, setSaved] = useState<ConsultationOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaved(null);
    setBusy(true);
    try {
      const created = await createConsultation(token, {
        appointment_id: Number(appointmentId),
        diagnosis,
        blood_pressure: bloodPressure || null,
        temperature: temperature || null,
        pulse: optionalNumber(pulse),
        spo2: optionalNumber(spo2),
        clinical_notes: notes,
      });
      setSaved(created);
      onSaved(created);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card accent="violet" className="max-w-2xl">
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField label="Appointment number" type="number" min={1} value={appointmentId} onChange={setAppointmentId} required accent="violet" />
        <FormField label="Diagnosis" value={diagnosis} onChange={setDiagnosis} required accent="violet" />
        <div className="grid gap-4 sm:grid-cols-4">
          <FormField label="Blood pressure" placeholder="120/80" value={bloodPressure} onChange={setBloodPressure} accent="violet" />
          <FormField label="Temperature" placeholder="98.6 F" value={temperature} onChange={setTemperature} accent="violet" />
          <FormField label="Pulse (bpm)" type="number" min={0} value={pulse} onChange={setPulse} accent="violet" />
          <FormField label="SpO₂ (%)" type="number" min={0} max={100} value={spo2} onChange={setSpo2} accent="violet" />
        </div>
        <TextAreaField label="Clinical notes" value={notes} onChange={setNotes} accent="violet" />
        {error && <ErrorAlert message={error} />}
        {saved && (
          <SuccessAlert>
            Consultation <span className="font-mono font-semibold">#{saved.id}</span> saved for patient{" "}
            <span className="font-mono">{saved.patient_uhid}</span>. You can now prescribe or order tests for it.
          </SuccessAlert>
        )}
        <PrimaryButton type="submit" accent="violet" disabled={busy}>
          {busy ? "Saving..." : "Save consultation"}
        </PrimaryButton>
      </form>
    </Card>
  );
}

function PrescriptionForm({ token, consultation }: { token: string; consultation: ConsultationOut | null }) {
  const [consultationId, setConsultationId] = useState(consultation ? String(consultation.id) : "");
  const [drug, setDrug] = useState("");
  const [dosage, setDosage] = useState("");
  const [frequency, setFrequency] = useState("");
  const [duration, setDuration] = useState("");
  const [added, setAdded] = useState<PrescriptionOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const created = await createPrescription(token, {
        consultation_id: Number(consultationId),
        drug_name: drug,
        dosage,
        frequency,
        duration,
      });
      setAdded((list) => [...list, created]);
      setDrug("");
      setDosage("");
      setFrequency("");
      setDuration("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card accent="violet">
        <form onSubmit={handleSubmit} className="space-y-4">
          <FormField label="Consultation number" type="number" min={1} value={consultationId} onChange={setConsultationId} required accent="violet" />
          <FormField label="Medicine" placeholder="Amlodipine" value={drug} onChange={setDrug} required accent="violet" />
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField label="Dosage" placeholder="5 mg" value={dosage} onChange={setDosage} required accent="violet" />
            <FormField label="Frequency" placeholder="Once daily" value={frequency} onChange={setFrequency} required accent="violet" />
            <FormField label="Duration" placeholder="30 days" value={duration} onChange={setDuration} required accent="violet" />
          </div>
          {error && <ErrorAlert message={error} />}
          <PrimaryButton type="submit" accent="violet" disabled={busy}>
            {busy ? "Adding..." : "Add to prescription"}
          </PrimaryButton>
        </form>
      </Card>
      <Card>
        <p className="text-sm font-medium text-stone-700">Added this session</p>
        {added.length === 0 && <EmptyState>Nothing yet. Each medicine is sent to the pharmacy as soon as it&apos;s added.</EmptyState>}
        <ul className="mt-2 divide-y divide-stone-100 text-sm">
          {added.map((p) => (
            <li key={p.id} className="py-2">
              <span className="font-medium text-stone-900">{p.drug_name}</span>{" "}
              <span className="text-stone-500">
                {p.dosage}, {p.frequency}, {p.duration}
              </span>
              <span className="ml-2 font-mono text-xs text-stone-400">{p.patient_uhid}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function LabTests({ token, consultation }: { token: string; consultation: ConsultationOut | null }) {
  const [appointmentId, setAppointmentId] = useState(consultation ? String(consultation.appointment_id) : "");
  const [testName, setTestName] = useState("");
  const [uhid, setUhid] = useState(consultation?.patient_uhid ?? "");
  const [tests, setTests] = useState<LabTestOut[] | null>(null);
  const [results, setResults] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function refresh(patientUhid: string) {
    setTests(await listLabTests(token, patientUhid));
  }

  async function attempt(action: () => Promise<void>) {
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
      <Card accent="violet">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            attempt(async () => {
              const order = await orderLabTest(token, Number(appointmentId), testName);
              setNotice(`${order.test_name} ordered (#${order.id}).`);
              setTestName("");
              setUhid(order.patient_uhid);
              await refresh(order.patient_uhid);
            });
          }}
        >
          <p className="text-sm font-medium text-stone-700">Order a test</p>
          <FormField label="Appointment number" type="number" min={1} value={appointmentId} onChange={setAppointmentId} required accent="violet" />
          <FormField label="Test" placeholder="CBC" value={testName} onChange={setTestName} required accent="violet" />
          <PrimaryButton type="submit" accent="violet">
            Order test
          </PrimaryButton>
        </form>
      </Card>

      <Card className="space-y-4">
        <form
          className="flex items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            attempt(() => refresh(uhid));
          }}
        >
          <div className="flex-1">
            <FormField label="Patient UHID" value={uhid} onChange={setUhid} required mono accent="violet" />
          </div>
          <SecondaryButton type="submit" className="py-2">
            Show tests
          </SecondaryButton>
        </form>
        {error && <ErrorAlert message={error} />}
        {notice && <SuccessAlert>{notice}</SuccessAlert>}
        {tests && tests.length === 0 && <EmptyState>No tests for this patient.</EmptyState>}
        <ul className="divide-y divide-stone-100">
          {tests?.map((t) => (
            <li key={t.id} className="space-y-2 py-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-stone-900">
                  {t.test_name} <span className="font-normal text-stone-400">· appt #{t.appointment_id}</span>
                </span>
                <StatusBadge status={t.status} />
              </div>
              {t.status === "COMPLETED" ? (
                <p className="rounded-lg bg-stone-50 px-3 py-2 text-sm text-stone-700">
                  {t.result}
                  {t.completed_at && <span className="ml-2 text-xs text-stone-400">{formatDateTime(t.completed_at)}</span>}
                </p>
              ) : (
                <div className="flex gap-2">
                  <input
                    placeholder="Result"
                    value={results[t.id] ?? ""}
                    onChange={(e) => setResults({ ...results, [t.id]: e.target.value })}
                    className="flex-1 rounded-lg border border-stone-300 px-3 py-1.5 text-sm focus:border-violet-600 focus:outline-none focus:ring-2 focus:ring-violet-100"
                  />
                  <SecondaryButton
                    type="button"
                    disabled={!results[t.id]?.trim()}
                    onClick={() =>
                      attempt(async () => {
                        await recordLabResult(token, t.id, results[t.id]);
                        setNotice(`Result recorded for ${t.test_name}.`);
                        await refresh(t.patient_uhid);
                      })
                    }
                  >
                    Record
                  </SecondaryButton>
                </div>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function PatientRecord({ token, initialUhid }: { token: string; initialUhid: string }) {
  const [uhid, setUhid] = useState(initialUhid);
  const [record, setRecord] = useState<{ patient: PatientResponse; visits: EHRVisit[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setRecord(null);
    try {
      setRecord(await getPatientEhr(token, uhid));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="space-y-6">
      <Card accent="violet" className="max-w-xl">
        <form onSubmit={handleSubmit} className="flex items-end gap-3">
          <div className="flex-1">
            <FormField label="Patient UHID" value={uhid} onChange={setUhid} required mono accent="violet" />
          </div>
          <PrimaryButton type="submit" accent="violet" className="w-auto">
            Open record
          </PrimaryButton>
        </form>
      </Card>
      {error && <ErrorAlert message={error} />}
      {record && (
        <div className="space-y-4">
          <Card>
            <p className="font-serif text-lg font-semibold">{record.patient.full_name}</p>
            <p className="text-sm text-stone-500">
              <span className="font-mono">{record.patient.uhid}</span> · {record.patient.age} yrs · {record.patient.gender} ·{" "}
              {record.patient.phone}
            </p>
          </Card>
          {record.visits.length === 0 && <EmptyState>No recorded visits yet.</EmptyState>}
          <ol className="relative space-y-4 border-l border-violet-200 pl-6">
            {record.visits.map((v) => (
              <li key={v.appointment_id} className="relative">
                <span className="absolute -left-[31px] top-5 h-3 w-3 rounded-full border-2 border-white bg-violet-600" />
                <Card className="space-y-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="font-medium text-stone-900">{v.diagnosis}</p>
                    <p className="text-xs text-stone-400">
                      {formatDateTime(v.visit_date)} · {v.doctor_id} · appt #{v.appointment_id}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs text-stone-600">
                    {v.blood_pressure && <Vital label="BP" value={v.blood_pressure} />}
                    {v.temperature && <Vital label="Temp" value={v.temperature} />}
                    {v.pulse !== null && <Vital label="Pulse" value={String(v.pulse)} />}
                    {v.spo2 !== null && <Vital label="SpO₂" value={`${v.spo2}%`} />}
                  </div>
                  {v.clinical_notes && <p className="text-sm text-stone-600">{v.clinical_notes}</p>}
                  {v.prescriptions.length > 0 && (
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-stone-400">Prescribed</p>
                      <ul className="mt-1 text-sm text-stone-700">
                        {v.prescriptions.map((p, i) => (
                          <li key={i}>
                            {p.drug_name} · {p.dosage}, {p.frequency}, {p.duration}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {v.lab_tests.length > 0 && (
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-stone-400">Lab tests</p>
                      <ul className="mt-1 space-y-1 text-sm text-stone-700">
                        {v.lab_tests.map((t, i) => (
                          <li key={i} className="flex items-center gap-2">
                            {t.test_name} <StatusBadge status={t.status} />
                            {t.result && <span className="text-stone-500">{t.result}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </Card>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

function Vital({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-md bg-violet-50 px-2 py-1">
      <span className="text-violet-700">{label}</span> {value}
    </span>
  );
}
