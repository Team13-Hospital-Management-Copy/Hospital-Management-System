"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useRequireAuth } from "@/lib/auth-context";
import {
  addBatch,
  dispenseMedicine,
  listBatches,
  listExpiryAlerts,
  listPrescriptions,
  type MedicineBatch,
  type PrescriptionOut,
} from "@/lib/api";
import { ErrorAlert, SuccessAlert } from "@/components/Alert";
import { Card } from "@/components/Card";
import { FormField, SelectField } from "@/components/FormField";
import { PrimaryButton, SecondaryButton } from "@/components/Button";
import { EmptyState, PageHeader, SectionTitle, StatusBadge, errorMessage } from "@/components/Page";

const EXPIRY_WINDOW_DAYS = 30;

export default function PharmacyPage() {
  const session = useRequireAuth();
  const [batches, setBatches] = useState<MedicineBatch[]>([]);
  const [expiring, setExpiring] = useState<MedicineBatch[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!session) return;
    try {
      const [all, soon] = await Promise.all([
        listBatches(session.token),
        listExpiryAlerts(session.token, EXPIRY_WINDOW_DAYS),
      ]);
      setBatches(all);
      setExpiring(soon);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [session]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (!session) return null;
  const lowStock = batches.filter((b) => b.low_stock);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pharmacy"
        description="Check a patient's prescriptions, dispense from stock, and watch for low stock and expiring batches."
      />
      {error && <ErrorAlert message={error} />}

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Batches in stock" value={batches.length} />
        <Stat label="Low stock" value={lowStock.length} tone={lowStock.length ? "amber" : undefined} />
        <Stat label={`Expiring in ${EXPIRY_WINDOW_DAYS} days`} value={expiring.length} tone={expiring.length ? "red" : undefined} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <DispensePanel token={session.token} batches={batches} onDispensed={refresh} />
        <AddBatchPanel token={session.token} onAdded={refresh} />
      </div>

      <Card className="overflow-x-auto">
        <SectionTitle>Stock</SectionTitle>
        {batches.length === 0 ? (
          <EmptyState>No batches yet. Add one above.</EmptyState>
        ) : (
          <table className="mt-3 w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-stone-400">
              <tr>
                <th className="py-2 font-medium">Medicine</th>
                <th className="py-2 font-medium">Batch</th>
                <th className="py-2 pr-8 text-right font-medium">Qty</th>
                <th className="py-2 font-medium">Expiry</th>
                <th className="py-2 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {batches.map((b) => {
                const expiringSoon = expiring.some((e) => e.id === b.id);
                return (
                  <tr key={b.id}>
                    <td className="py-2 font-medium text-stone-900">{b.medicine_name}</td>
                    <td className="py-2 font-mono text-xs text-stone-500">{b.batch_number}</td>
                    <td className="py-2 pr-8 text-right tabular-nums">{b.quantity}</td>
                    <td className="py-2 text-stone-600">{b.expiry_date}</td>
                    <td className="space-x-1 py-2 text-right">
                      {b.low_stock && <StatusBadge status="LOW STOCK" tone="amber" />}
                      {expiringSoon && <StatusBadge status="EXPIRING" tone="red" />}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "amber" | "red" }) {
  const colour = tone === "red" ? "text-red-700" : tone === "amber" ? "text-amber-700" : "text-stone-900";
  return (
    <Card className="py-4">
      <p className="text-xs uppercase tracking-wide text-stone-400">{label}</p>
      <p className={`mt-1 font-serif text-3xl font-semibold tabular-nums ${colour}`}>{value}</p>
    </Card>
  );
}

function DispensePanel({
  token,
  batches,
  onDispensed,
}: {
  token: string;
  batches: MedicineBatch[];
  onDispensed: () => void;
}) {
  const [uhid, setUhid] = useState("");
  const [prescriptions, setPrescriptions] = useState<PrescriptionOut[] | null>(null);
  const [batchId, setBatchId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const inStock = batches.filter((b) => b.quantity > 0);

  async function lookUp() {
    setError(null);
    setNotice(null);
    try {
      setPrescriptions(await listPrescriptions(token, uhid));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function handleDispense(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    try {
      const result = await dispenseMedicine(token, {
        batch_id: Number(batchId || inStock[0]?.id),
        patient_uhid: uhid,
        quantity: Number(quantity),
      });
      setNotice(`${result.dispensed_quantity} × ${result.batch.medicine_name} dispensed. ${result.batch.quantity} left in this batch.`);
      onDispensed();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card accent="teal" className="space-y-4">
      <SectionTitle>Dispense</SectionTitle>
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <FormField label="Patient UHID" value={uhid} onChange={setUhid} mono />
        </div>
        <SecondaryButton type="button" className="py-2" disabled={!uhid} onClick={lookUp}>
          Prescriptions
        </SecondaryButton>
      </div>
      {prescriptions && (
        <div className="rounded-lg bg-stone-50 px-3 py-2">
          {prescriptions.length === 0 ? (
            <EmptyState>No prescriptions for this patient.</EmptyState>
          ) : (
            <ul className="space-y-1 text-sm text-stone-700">
              {prescriptions.map((p) => (
                <li key={p.id}>
                  <span className="font-medium">{p.drug_name}</span> · {p.dosage}, {p.frequency}, {p.duration}
                  <span className="ml-1 text-xs text-stone-400">by {p.doctor_username}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <form onSubmit={handleDispense} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-[1fr_7rem]">
          <SelectField
            label="Batch"
            value={batchId || String(inStock[0]?.id ?? "")}
            onChange={setBatchId}
            options={
              inStock.length
                ? inStock.map((b) => ({
                    value: String(b.id),
                    label: `${b.medicine_name} · ${b.batch_number} (${b.quantity} left, exp ${b.expiry_date})`,
                  }))
                : [{ value: "", label: "No stock" }]
            }
          />
          <FormField label="Quantity" type="number" min={1} value={quantity} onChange={setQuantity} required />
        </div>
        {error && <ErrorAlert message={error} />}
        {notice && <SuccessAlert>{notice}</SuccessAlert>}
        <PrimaryButton type="submit" disabled={!uhid || inStock.length === 0}>
          Dispense
        </PrimaryButton>
      </form>
    </Card>
  );
}

function AddBatchPanel({ token, onAdded }: { token: string; onAdded: () => void }) {
  const [name, setName] = useState("");
  const [batchNumber, setBatchNumber] = useState("");
  const [quantity, setQuantity] = useState("");
  const [threshold, setThreshold] = useState("10");
  const [expiry, setExpiry] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    try {
      await addBatch(token, {
        medicine_name: name,
        batch_number: batchNumber,
        quantity: Number(quantity),
        low_stock_threshold: Number(threshold),
        expiry_date: expiry,
      });
      setNotice(`Batch ${batchNumber} of ${name} added.`);
      setName("");
      setBatchNumber("");
      setQuantity("");
      setExpiry("");
      onAdded();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card className="space-y-4">
      <SectionTitle>Receive stock</SectionTitle>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Medicine" value={name} onChange={setName} required />
          <FormField label="Batch number" value={batchNumber} onChange={setBatchNumber} required mono />
          <FormField label="Quantity" type="number" min={1} value={quantity} onChange={setQuantity} required />
          <FormField label="Low-stock alert at" type="number" min={0} value={threshold} onChange={setThreshold} required />
        </div>
        <FormField label="Expiry date" type="date" value={expiry} onChange={setExpiry} required />
        {error && <ErrorAlert message={error} />}
        {notice && <SuccessAlert>{notice}</SuccessAlert>}
        <PrimaryButton type="submit">Add batch</PrimaryButton>
      </form>
    </Card>
  );
}
