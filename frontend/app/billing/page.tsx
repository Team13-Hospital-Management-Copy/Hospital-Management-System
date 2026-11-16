"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useRequireAuth } from "@/lib/auth-context";
import {
  ApiError,
  addBillItem,
  applyDiscount,
  consolidateBill,
  createDiscountScheme,
  deactivateDiscountScheme,
  getBill,
  listDiscountSchemes,
  listTariffs,
  openBill,
  recordPayment,
  setTariff,
  type BillOut,
  type DiscountSchemeOut,
  type TariffOut,
} from "@/lib/api";
import { ErrorAlert, SuccessAlert } from "@/components/Alert";
import { Card } from "@/components/Card";
import { FormField, SelectField } from "@/components/FormField";
import { PrimaryButton, SecondaryButton } from "@/components/Button";
import { EmptyState, PageHeader, SectionTitle, StatusBadge, Tabs, errorMessage, formatDateTime, rupees } from "@/components/Page";

const CATEGORIES = ["CONSULTATION", "LAB", "PHARMACY", "ROOM", "OTHER"] as const;
const PAYMENT_METHODS = ["CASH", "CARD", "UPI"] as const;
// Mirrors backend DEFAULT_TARIFF: a "*" row is the category's fallback price.
const CATEGORY_DEFAULT = "*";

type Tab = "bills" | "setup";

export default function BillingPage() {
  const session = useRequireAuth();
  const [tab, setTab] = useState<Tab>("bills");
  if (!session) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Billing"
        description="US-17: build the bill from the visit's records, apply a discount scheme, and take payments with an instant receipt."
      />
      <Tabs
        tabs={[
          { id: "bills", label: "Bills (receptionist)" },
          { id: "setup", label: "Price list & schemes (admin)" },
        ]}
        active={tab}
        onChange={setTab}
      />
      {/* Both stay mounted so switching tabs doesn't lose the open bill. */}
      <div hidden={tab !== "bills"}>
        <Bills token={session.token} />
      </div>
      <div hidden={tab !== "setup"}>
        <Setup token={session.token} />
      </div>
    </div>
  );
}

// --- Bills ----------------------------------------------------------------------------------------

/** Turns an API failure into a message plus, for a consolidate with unpriced items, the list of them. */
function describe(err: unknown): { message: string; missing: string[] } {
  if (err instanceof ApiError && err.detail && typeof err.detail === "object" && "missing_prices" in err.detail) {
    return { message: err.message, missing: (err.detail as { missing_prices: string[] }).missing_prices };
  }
  return { message: errorMessage(err), missing: [] };
}

function Bills({ token }: { token: string }) {
  const [bill, setBill] = useState<BillOut | null>(null);
  const [lookupId, setLookupId] = useState("");
  const [uhid, setUhid] = useState("");
  const [appointmentId, setAppointmentId] = useState("");
  const [admissionId, setAdmissionId] = useState("");
  const [error, setError] = useState<{ message: string; missing: string[] } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function run(action: () => Promise<BillOut>, message?: string) {
    setError(null);
    setNotice(null);
    try {
      const updated = await action();
      setBill(updated);
      if (message) setNotice(message);
    } catch (err) {
      setError(describe(err));
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[20rem_1fr]">
      <div className="space-y-6">
        <Card accent="rose">
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              run(
                () =>
                  openBill(token, {
                    patient_uhid: uhid,
                    appointment_id: appointmentId ? Number(appointmentId) : null,
                    admission_id: admissionId ? Number(admissionId) : null,
                  }),
                "Bill opened. Press “Pull in visit charges” to fill it."
              );
            }}
          >
            <SectionTitle>New bill</SectionTitle>
            <FormField label="Patient UHID" value={uhid} onChange={setUhid} required mono accent="rose" />
            <FormField label="Appointment number (optional)" type="number" min={1} value={appointmentId} onChange={setAppointmentId} accent="rose" />
            <FormField label="Admission number (optional)" type="number" min={1} value={admissionId} onChange={setAdmissionId} accent="rose" />
            <PrimaryButton type="submit" accent="rose">
              Open bill
            </PrimaryButton>
          </form>
        </Card>
        <Card>
          <form
            className="flex items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              run(() => getBill(token, Number(lookupId)));
            }}
          >
            <div className="flex-1">
              <FormField label="Find bill number" type="number" min={1} value={lookupId} onChange={setLookupId} required accent="rose" />
            </div>
            <SecondaryButton type="submit" className="py-2">
              Open
            </SecondaryButton>
          </form>
        </Card>
      </div>

      <div className="space-y-4">
        {error && (
          <div className="space-y-2">
            <ErrorAlert message={error.message} />
            {error.missing.length > 0 && (
              <Card className="py-4">
                <p className="text-sm text-stone-700">
                  Ask an administrator to add these to the price list, then try again:
                </p>
                <ul className="mt-2 list-inside list-disc text-sm text-stone-600">
                  {error.missing.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
        )}
        {notice && <SuccessAlert>{notice}</SuccessAlert>}
        {bill ? (
          <BillView token={token} bill={bill} run={run} />
        ) : (
          <Card className="flex min-h-48 items-center justify-center">
            <EmptyState>Open a new bill or find an existing one.</EmptyState>
          </Card>
        )}
      </div>
    </div>
  );
}

function BillView({
  token,
  bill,
  run,
}: {
  token: string;
  bill: BillOut;
  run: (action: () => Promise<BillOut>, message?: string) => Promise<void>;
}) {
  const [schemes, setSchemes] = useState<DiscountSchemeOut[]>([]);
  const [itemCategory, setItemCategory] = useState<string>("OTHER");
  const [itemDescription, setItemDescription] = useState("");
  const [itemAmount, setItemAmount] = useState("");
  const [discountMode, setDiscountMode] = useState<"scheme" | "percent" | "amount">("scheme");
  const [schemeId, setSchemeId] = useState("");
  const [discountValue, setDiscountValue] = useState("");
  const [discountReason, setDiscountReason] = useState("");
  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState<string>("CASH");

  useEffect(() => {
    listDiscountSchemes(token).then(setSchemes).catch(() => setSchemes([]));
  }, [token]);

  const paid = bill.status === "PAID";
  const anyPayment = bill.payments.length > 0;
  const selectedScheme = schemeId || String(schemes[0]?.id ?? "");
  const lastReceipt = bill.payments[bill.payments.length - 1];

  return (
    <Card accent="rose" className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-serif text-xl font-semibold">Bill #{bill.id}</p>
          <p className="mt-1 text-sm text-stone-500">
            Patient <span className="font-mono">{bill.patient_uhid}</span>
            {bill.appointment_id && <> · appointment #{bill.appointment_id}</>}
            {bill.admission_id && <> · admission #{bill.admission_id}</>}
          </p>
          <p className="text-xs text-stone-400">Opened {formatDateTime(bill.created_at)}</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={bill.status} />
          {!paid && (bill.appointment_id || bill.admission_id) && (
            <SecondaryButton type="button" onClick={() => run(() => consolidateBill(token, bill.id), "Visit charges pulled in.")}>
              Pull in visit charges
            </SecondaryButton>
          )}
        </div>
      </div>

      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-stone-400">
          <tr>
            <th className="py-2 font-medium">Item</th>
            <th className="py-2 text-right font-medium">Qty</th>
            <th className="py-2 text-right font-medium">Rate</th>
            <th className="py-2 text-right font-medium">Amount</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {bill.line_items.length === 0 && (
            <tr>
              <td colSpan={4} className="py-4 text-center text-stone-400">
                No items yet.
              </td>
            </tr>
          )}
          {bill.line_items.map((item) => (
            <tr key={item.id}>
              <td className="py-2">
                <span className="text-stone-900">{item.description}</span>
                <span className="ml-2 text-xs text-stone-400">{item.category}</span>
              </td>
              <td className="py-2 text-right tabular-nums">{item.quantity}</td>
              <td className="py-2 text-right tabular-nums text-stone-500">{item.unit_price ? rupees(item.unit_price) : "-"}</td>
              <td className="py-2 text-right tabular-nums">{rupees(item.amount)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot className="text-sm">
          <Row label="Subtotal" value={rupees(bill.subtotal)} />
          {Number(bill.subtotal) !== Number(bill.total) && (
            <Row
              label={`Discount${bill.discount_percent ? ` (${Number(bill.discount_percent)}%)` : ""}${bill.discount_reason ? ` · ${bill.discount_reason}` : ""}`}
              value={`− ${rupees(Number(bill.subtotal) - Number(bill.total))}`}
            />
          )}
          <Row label="Total" value={rupees(bill.total)} strong />
          <Row label="Paid" value={rupees(bill.amount_paid)} />
          <Row label="Balance due" value={rupees(bill.balance_due)} strong />
        </tfoot>
      </table>

      {lastReceipt && (
        <SuccessAlert>
          Receipt <span className="font-mono font-semibold">{lastReceipt.receipt_number}</span>: {rupees(lastReceipt.amount)} by{" "}
          {lastReceipt.method}, {formatDateTime(lastReceipt.paid_at)}.
        </SuccessAlert>
      )}

      {!paid && (
        <div className="grid gap-6 border-t border-stone-100 pt-6 md:grid-cols-2">
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              run(() => recordPayment(token, bill.id, { amount: payAmount, method: payMethod }), "Payment recorded.").then(() =>
                setPayAmount("")
              );
            }}
          >
            <p className="text-sm font-medium text-stone-700">Take payment</p>
            <div className="grid grid-cols-[1fr_7rem] gap-3">
              <FormField label="Amount" type="number" min={0} value={payAmount} onChange={setPayAmount} required accent="rose" />
              <SelectField
                label="Method"
                value={payMethod}
                onChange={setPayMethod}
                options={PAYMENT_METHODS.map((m) => ({ value: m, label: m }))}
                accent="rose"
              />
            </div>
            <div className="flex gap-2">
              <PrimaryButton type="submit" accent="rose">
                Record payment
              </PrimaryButton>
              <SecondaryButton type="button" className="shrink-0" onClick={() => setPayAmount(bill.balance_due)}>
                Full balance
              </SecondaryButton>
            </div>
          </form>

          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              const payload =
                discountMode === "scheme"
                  ? { scheme_id: Number(selectedScheme) }
                  : discountMode === "percent"
                    ? { discount_percent: discountValue, reason: discountReason }
                    : { discount_amount: discountValue, reason: discountReason };
              run(() => applyDiscount(token, bill.id, payload), "Discount applied.");
            }}
          >
            <p className="text-sm font-medium text-stone-700">Discount</p>
            {anyPayment ? (
              <EmptyState>Discounts can&apos;t change once a payment has been taken.</EmptyState>
            ) : (
              <>
                <SelectField
                  label="Type"
                  value={discountMode}
                  onChange={(v) => setDiscountMode(v as typeof discountMode)}
                  options={[
                    { value: "scheme", label: "Configured scheme" },
                    { value: "percent", label: "One-off percentage" },
                    { value: "amount", label: "One-off flat amount" },
                  ]}
                  accent="rose"
                />
                {discountMode === "scheme" ? (
                  <SelectField
                    label="Scheme"
                    value={selectedScheme}
                    onChange={setSchemeId}
                    options={
                      schemes.length
                        ? schemes.map((s) => ({ value: String(s.id), label: `${s.name} (${schemeValue(s)})` }))
                        : [{ value: "", label: "No active schemes" }]
                    }
                    accent="rose"
                  />
                ) : (
                  <div className="grid grid-cols-[7rem_1fr] gap-3">
                    <FormField
                      label={discountMode === "percent" ? "Percent" : "Amount"}
                      type="number"
                      min={0}
                      value={discountValue}
                      onChange={setDiscountValue}
                      required
                      accent="rose"
                    />
                    <FormField label="Reason (required)" value={discountReason} onChange={setDiscountReason} required accent="rose" />
                  </div>
                )}
                <SecondaryButton type="submit" disabled={discountMode === "scheme" && !selectedScheme}>
                  Apply discount
                </SecondaryButton>
              </>
            )}
          </form>

          <form
            className="space-y-3 md:col-span-2"
            onSubmit={(e) => {
              e.preventDefault();
              run(
                () => addBillItem(token, bill.id, { category: itemCategory, description: itemDescription, amount: itemAmount }),
                "Item added."
              ).then(() => {
                setItemDescription("");
                setItemAmount("");
              });
            }}
          >
            <p className="text-sm font-medium text-stone-700">Add a manual item</p>
            <div className="grid gap-3 sm:grid-cols-[10rem_1fr_8rem_auto] sm:items-end">
              <SelectField
                label="Category"
                value={itemCategory}
                onChange={setItemCategory}
                options={CATEGORIES.map((c) => ({ value: c, label: c }))}
                accent="rose"
              />
              <FormField label="Description" value={itemDescription} onChange={setItemDescription} required accent="rose" />
              <FormField label="Amount" type="number" min={0} value={itemAmount} onChange={setItemAmount} required accent="rose" />
              <SecondaryButton type="submit" className="py-2">
                Add
              </SecondaryButton>
            </div>
          </form>
        </div>
      )}

      {bill.payments.length > 1 && (
        <div className="border-t border-stone-100 pt-4">
          <p className="text-sm font-medium text-stone-700">All receipts</p>
          <ul className="mt-2 divide-y divide-stone-100 text-sm">
            {bill.payments.map((p) => (
              <li key={p.id} className="flex justify-between py-1.5">
                <span className="font-mono text-xs text-stone-600">{p.receipt_number}</span>
                <span>
                  {rupees(p.amount)} · {p.method}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <tr className={strong ? "font-semibold text-stone-900" : "text-stone-500"}>
      <td colSpan={3} className="pt-2 text-right">
        {label}
      </td>
      <td className="pt-2 text-right tabular-nums">{value}</td>
    </tr>
  );
}

function schemeValue(s: DiscountSchemeOut): string {
  return s.discount_percent !== null ? `${Number(s.discount_percent)}%` : rupees(s.discount_amount ?? 0);
}

// --- Setup (administrators) -----------------------------------------------------------------------

function Setup({ token }: { token: string }) {
  const [tariffs, setTariffs] = useState<TariffOut[]>([]);
  const [schemes, setSchemes] = useState<DiscountSchemeOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [category, setCategory] = useState<string>("CONSULTATION");
  const [itemName, setItemName] = useState("");
  const [price, setPrice] = useState("");

  const [schemeName, setSchemeName] = useState("");
  const [schemeKind, setSchemeKind] = useState<"percent" | "amount">("percent");
  const [schemeAmount, setSchemeAmount] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [t, s] = await Promise.all([listTariffs(token), listDiscountSchemes(token, true)]);
      setTariffs(t);
      setSchemes(s);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [token]);

  useEffect(() => {
    refresh();
  }, [refresh]);

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

  function handleTariff(event: FormEvent) {
    event.preventDefault();
    const name = itemName.trim() || CATEGORY_DEFAULT;
    attempt(() => setTariff(token, { category, item_name: name, unit_price: price }), `Price saved for ${category} · ${name}.`).then(() => {
      setItemName("");
      setPrice("");
    });
  }

  function handleScheme(event: FormEvent) {
    event.preventDefault();
    const payload =
      schemeKind === "percent"
        ? { name: schemeName, discount_percent: schemeAmount }
        : { name: schemeName, discount_amount: schemeAmount };
    attempt(() => createDiscountScheme(token, payload), `Scheme “${schemeName}” created.`).then(() => {
      setSchemeName("");
      setSchemeAmount("");
    });
  }

  return (
    <div className="space-y-4">
      {error && <ErrorAlert message={error} />}
      {notice && <SuccessAlert>{notice}</SuccessAlert>}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card accent="violet" className="space-y-4">
          <SectionTitle>Price list</SectionTitle>
          <p className="text-sm text-stone-500">
            Consultations are priced by the doctor&apos;s department, lab tests by test name, medicines per unit, and rooms per day by
            ward. Leave the item blank to set the category&apos;s default price.
          </p>
          <form onSubmit={handleTariff} className="grid grid-cols-2 gap-3 sm:items-end">
            <SelectField
              label="Category"
              value={category}
              onChange={setCategory}
              options={CATEGORIES.map((c) => ({ value: c, label: c }))}
              accent="violet"
            />
            <FormField label="Item" placeholder="e.g. Cardiology, CBC, General" value={itemName} onChange={setItemName} accent="violet" />
            <FormField label="Price" type="number" min={0} value={price} onChange={setPrice} required accent="violet" />
            <SecondaryButton type="submit" className="py-2">
              Save
            </SecondaryButton>
          </form>
          {tariffs.length === 0 ? (
            <EmptyState>No prices yet.</EmptyState>
          ) : (
            <table className="w-full text-left text-sm">
              <tbody className="divide-y divide-stone-100">
                {tariffs.map((t) => (
                  <tr key={t.id}>
                    <td className="py-1.5 text-xs text-stone-400">{t.category}</td>
                    <td className="py-1.5">{t.item_name === CATEGORY_DEFAULT ? <em className="text-stone-500">default</em> : t.item_name}</td>
                    <td className="py-1.5 text-right tabular-nums">{rupees(t.unit_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card accent="violet" className="space-y-4">
          <SectionTitle>Discount schemes</SectionTitle>
          <form onSubmit={handleScheme} className="grid grid-cols-2 gap-3 sm:items-end">
            <FormField label="Name" placeholder="Senior citizen" value={schemeName} onChange={setSchemeName} required accent="violet" />
            <SelectField
              label="Type"
              value={schemeKind}
              onChange={(v) => setSchemeKind(v as typeof schemeKind)}
              options={[
                { value: "percent", label: "Percent" },
                { value: "amount", label: "Flat ₹" },
              ]}
              accent="violet"
            />
            <FormField label="Value" type="number" min={0} value={schemeAmount} onChange={setSchemeAmount} required accent="violet" />
            <SecondaryButton type="submit" className="py-2">
              Create
            </SecondaryButton>
          </form>
          {schemes.length === 0 ? (
            <EmptyState>No schemes yet.</EmptyState>
          ) : (
            <ul className="divide-y divide-stone-100 text-sm">
              {schemes.map((s) => (
                <li key={s.id} className="flex items-center justify-between py-2">
                  <span className={s.is_active ? "text-stone-900" : "text-stone-400 line-through"}>
                    {s.name} <span className="text-stone-500">· {schemeValue(s)}</span>
                  </span>
                  {s.is_active ? (
                    <SecondaryButton
                      type="button"
                      onClick={() => attempt(() => deactivateDiscountScheme(token, s.id), `“${s.name}” deactivated.`)}
                    >
                      Deactivate
                    </SecondaryButton>
                  ) : (
                    <StatusBadge status="INACTIVE" />
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
