"use client";

import { useState, type FormEvent } from "react";
import { useRequireAuth } from "@/lib/auth-context";
import { fetchAuthorizedFile, getReportSummary, type ReportSummary } from "@/lib/api";
import { ErrorAlert } from "@/components/Alert";
import { Card } from "@/components/Card";
import { FormField } from "@/components/FormField";
import { PrimaryButton, SecondaryButton } from "@/components/Button";
import { PageHeader, errorMessage, rupees } from "@/components/Page";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const session = useRequireAuth();
  const [start, setStart] = useState(isoDaysAgo(30));
  const [end, setEnd] = useState(isoDaysAgo(0));
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!session) return null;
  const token = session.token;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      setSummary(await getReportSummary(token, start, end));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function download(format: "csv" | "pdf") {
    setError(null);
    try {
      const blob = await fetchAuthorizedFile(token, `/admin/reports/export?start_date=${start}&end_date=${end}&format=${format}`);
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `hms-report-${start}-to-${end}.${format}`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Operational reports" description="US-20: OPD footfall, revenue and bed occupancy for a date range, exportable as PDF or CSV." />

      <Card accent="violet">
        <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <FormField label="From" type="date" value={start} onChange={setStart} required accent="violet" />
          <FormField label="To" type="date" value={end} onChange={setEnd} required accent="violet" />
          <PrimaryButton type="submit" accent="violet" className="w-auto">
            Run report
          </PrimaryButton>
        </form>
      </Card>

      {error && <ErrorAlert message={error} />}

      {summary && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="OPD footfall" value={summary.opd_footfall.toLocaleString()} />
            <Metric label="Revenue collected" value={rupees(summary.revenue)} />
            <Metric label="Admissions" value={summary.admissions_in_range.toLocaleString()} />
            <Metric label="Bed occupancy" value={`${(summary.bed_occupancy_rate * 100).toFixed(1)}%`} />
          </div>
          <Card className="space-y-3">
            <div className="flex justify-between text-sm text-stone-600">
              <span>Bed-days used</span>
              <span className="tabular-nums">
                {summary.occupied_bed_days} of {summary.available_bed_days}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-stone-100">
              <div
                className="h-full rounded-full bg-violet-600"
                style={{ width: `${Math.min(100, summary.bed_occupancy_rate * 100)}%` }}
              />
            </div>
            <div className="flex gap-2 pt-2">
              <SecondaryButton type="button" onClick={() => download("pdf")}>
                Download PDF
              </SecondaryButton>
              <SecondaryButton type="button" onClick={() => download("csv")}>
                Download CSV
              </SecondaryButton>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Card className="py-4">
      <p className="text-xs uppercase tracking-wide text-stone-400">{label}</p>
      <p className="mt-1 font-serif text-2xl font-semibold tabular-nums text-stone-900">{value}</p>
    </Card>
  );
}
