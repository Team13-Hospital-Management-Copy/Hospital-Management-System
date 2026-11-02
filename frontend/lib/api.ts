const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  options: { method?: string; token?: string | null; body?: unknown } = {}
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.token) headers["Authorization"] = `Bearer ${options.token}`;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let message = response.statusText;
    let detail: unknown;
    try {
      const data = await response.json();
      detail = data.detail;
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail)) message = detail.map((d) => d?.msg ?? String(d)).join("; ");
      else if (detail && typeof detail === "object" && "message" in detail) message = String(detail.message);
      else message = JSON.stringify(detail ?? data);
    } catch {
      // body wasn't JSON; fall back to statusText
    }
    throw new ApiError(response.status, message, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// --- Auth (US-01 / US-03) ----------------------------------------------------------------------

export interface LoginResponse {
  status: string;
  message: string;
  token: string | null;
}

export function login(username: string, password: string) {
  return request<LoginResponse>("/auth/login", { method: "POST", body: { username, password } });
}

export function logout(token: string) {
  return request<{ status: string; message: string }>("/auth/logout", { method: "POST", token });
}

// --- Patients (US-05) ---------------------------------------------------------------------------

export interface PatientCreate {
  full_name: string;
  age: number;
  gender: string;
  phone: string;
  address?: string;
}

export interface PatientResponse extends PatientCreate {
  id: number;
  uhid: string;
}

export function registerPatient(token: string, payload: PatientCreate) {
  return request<PatientResponse>("/patients/", { method: "POST", token, body: payload });
}

// --- Doctors (US-07) -----------------------------------------------------------------------------

export interface ScheduleBlock {
  weekday: number; // 0 = Monday ... 6 = Sunday
  start_time: string; // "HH:MM"
  end_time: string; // "HH:MM"
}

export interface DoctorCreate {
  full_name: string;
  specialization: string;
  department: string;
  slot_minutes: number;
  schedule: ScheduleBlock[];
}

export interface DoctorOut extends DoctorCreate {
  doctor_id: string;
  is_active: boolean;
}

export function createDoctor(token: string, payload: DoctorCreate) {
  return request<DoctorOut>("/doctors", { method: "POST", token, body: payload });
}

export function listDoctors(token: string) {
  return request<DoctorOut[]>("/doctors", { token });
}

export function getAvailableSlots(token: string, doctorId: string, day: string) {
  return request<{ doctor_id: string; day: string; available: string[] }>(
    `/doctors/${encodeURIComponent(doctorId)}/available-slots?day=${day}`,
    { token }
  );
}

// --- Appointments (US-08 / US-11) -----------------------------------------------------------------

export interface AppointmentOut {
  id: number;
  patient_uhid: string;
  doctor_id: string;
  slot_start: string;
  status: string;
  rescheduled_count: number;
}

export function bookOpdAppointment(
  token: string,
  payload: { patient_uhid: string; doctor_id: string; slot_start: string }
) {
  return request<AppointmentOut>("/appointments/opd", { method: "POST", token, body: payload });
}

export interface NotificationOut {
  id: number;
  kind: string;
  channel: string;
  status: string;
  scheduled_for: string;
  sent_at: string | null;
  message: string;
}

export function getAppointmentNotifications(token: string, appointmentId: number) {
  return request<NotificationOut[]>(`/appointments/${appointmentId}/notifications`, { token });
}

export function getAppointment(token: string, appointmentId: number) {
  return request<AppointmentOut>(`/appointments/${appointmentId}`, { token });
}

// --- Reschedule / cancel (US-10) ------------------------------------------------------------------

export function cancelAppointment(token: string, appointmentId: number) {
  return request<AppointmentOut>(`/appointments/${appointmentId}/cancel`, { method: "POST", token });
}

export function rescheduleAppointment(token: string, appointmentId: number, newSlotStart: string) {
  return request<AppointmentOut>(`/appointments/${appointmentId}/reschedule`, {
    method: "POST",
    token,
    body: { new_slot_start: newSlotStart },
  });
}

// --- Patient search (US-06) ---------------------------------------------------------------------

export function searchPatients(token: string, query: { uhid?: string; name?: string; phone?: string }) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) if (value) params.set(key, value);
  return request<PatientResponse[]>(`/patients/search?${params}`, { token });
}

// --- Consultations, prescriptions & EHR (US-12, US-13, US-15) -----------------------------------

export interface ConsultationCreate {
  appointment_id: number;
  diagnosis: string;
  blood_pressure?: string | null;
  temperature?: string | null;
  pulse?: number | null;
  spo2?: number | null;
  clinical_notes?: string;
}

export interface ConsultationOut extends ConsultationCreate {
  id: number;
  patient_uhid: string;
  created_at: string;
}

export function createConsultation(token: string, payload: ConsultationCreate) {
  return request<ConsultationOut>("/consultations", { method: "POST", token, body: payload });
}

export interface PrescriptionCreate {
  consultation_id: number;
  drug_name: string;
  dosage: string;
  frequency: string;
  duration: string;
}

export interface PrescriptionOut extends PrescriptionCreate {
  id: number;
  patient_uhid: string;
  doctor_username: string;
  created_at: string;
}

export function createPrescription(token: string, payload: PrescriptionCreate) {
  return request<PrescriptionOut>("/prescriptions", { method: "POST", token, body: payload });
}

export function listPrescriptions(token: string, patientUhid: string) {
  return request<PrescriptionOut[]>(`/prescriptions/${encodeURIComponent(patientUhid)}`, { token });
}

export interface EHRVisit {
  appointment_id: number;
  visit_date: string;
  doctor_id: string;
  diagnosis: string;
  blood_pressure: string | null;
  temperature: string | null;
  pulse: number | null;
  spo2: number | null;
  clinical_notes: string;
  prescriptions: { drug_name: string; dosage: string; frequency: string; duration: string }[];
  lab_tests: { test_name: string; status: string; result: string | null }[];
}

export function getPatientEhr(token: string, patientUhid: string) {
  return request<{ patient: PatientResponse; visits: EHRVisit[] }>(
    `/patients/${encodeURIComponent(patientUhid)}/ehr`,
    { token }
  );
}

// --- Lab tests (US-14) --------------------------------------------------------------------------

export interface LabTestOut {
  id: number;
  appointment_id: number;
  patient_uhid: string;
  test_name: string;
  status: string;
  ordered_by: string;
  result: string | null;
  ordered_at: string;
  completed_at: string | null;
}

export function orderLabTest(token: string, appointmentId: number, testName: string) {
  return request<LabTestOut>("/lab-tests", {
    method: "POST",
    token,
    body: { appointment_id: appointmentId, test_name: testName },
  });
}

export function recordLabResult(token: string, labTestId: number, result: string) {
  return request<LabTestOut>(`/lab-tests/${labTestId}/result`, { method: "POST", token, body: { result } });
}

export function listLabTests(token: string, patientUhid: string) {
  return request<LabTestOut[]>(`/lab-tests/${encodeURIComponent(patientUhid)}`, { token });
}

// --- Pharmacy inventory & dispensing -----------------------------------------------------------

export interface MedicineBatch {
  id: number;
  medicine_name: string;
  batch_number: string;
  quantity: number;
  low_stock_threshold: number;
  expiry_date: string;
  low_stock: boolean;
}

export function listBatches(token: string) {
  return request<MedicineBatch[]>("/pharmacy/batches", { token });
}

export function addBatch(
  token: string,
  payload: { medicine_name: string; batch_number: string; quantity: number; low_stock_threshold: number; expiry_date: string }
) {
  return request<MedicineBatch>("/pharmacy/batches", { method: "POST", token, body: payload });
}

export function dispenseMedicine(token: string, payload: { batch_id: number; patient_uhid: string; quantity: number }) {
  return request<{ message: string; dispense_id: number; batch: MedicineBatch; dispensed_quantity: number }>(
    "/pharmacy/dispense",
    { method: "POST", token, body: payload }
  );
}

export function listLowStock(token: string) {
  return request<MedicineBatch[]>("/pharmacy/low-stock", { token });
}

export function listExpiryAlerts(token: string, withinDays: number) {
  return request<MedicineBatch[]>(`/pharmacy/expiry-alerts?within_days=${withinDays}`, { token });
}

// --- Admission & discharge (US-16) -------------------------------------------------------------

export interface BedOut {
  id: number;
  bed_number: string;
  ward: string;
  is_active: boolean;
  occupied: boolean;
}

export interface AdmissionOut {
  id: number;
  patient_uhid: string;
  bed_id: number;
  admitted_at: string;
  discharged_at: string | null;
  diagnosis: string;
  treatment: string;
  follow_up_instructions: string;
}

export interface DischargeSummary {
  admission_id: number;
  patient_uhid: string;
  patient_name: string;
  bed_number: string;
  ward: string;
  admitted_at: string;
  discharged_at: string;
  diagnosis: string;
  treatment: string;
  follow_up_instructions: string;
}

export function listBeds(token: string) {
  return request<BedOut[]>("/inpatient/beds", { token });
}

export function addBed(token: string, payload: { bed_number: string; ward: string }) {
  return request<BedOut>("/inpatient/beds", { method: "POST", token, body: payload });
}

export function admitPatient(
  token: string,
  payload: { patient_uhid: string; bed_id: number; diagnosis: string; treatment: string; follow_up_instructions: string }
) {
  return request<AdmissionOut>("/inpatient/admissions", { method: "POST", token, body: payload });
}

export function dischargePatient(token: string, admissionId: number) {
  return request<DischargeSummary>(`/inpatient/admissions/${admissionId}/discharge`, { method: "POST", token });
}

// --- Billing (US-17) ----------------------------------------------------------------------------

export interface TariffOut {
  id: number;
  category: string;
  item_name: string;
  unit_price: string;
}

export interface DiscountSchemeOut {
  id: number;
  name: string;
  discount_percent: string | null;
  discount_amount: string | null;
  is_active: boolean;
}

export interface BillLineItem {
  id: number;
  category: string;
  description: string;
  quantity: number;
  unit_price: string | null;
  amount: string;
  source_type: string | null;
  source_id: number | null;
}

export interface PaymentOut {
  id: number;
  amount: string;
  method: string;
  receipt_number: string;
  paid_at: string;
}

export interface BillOut {
  id: number;
  patient_uhid: string;
  appointment_id: number | null;
  admission_id: number | null;
  status: string;
  line_items: BillLineItem[];
  subtotal: string;
  discount_percent: string | null;
  discount_amount: string | null;
  discount_reason: string;
  discount_scheme_id: number | null;
  total: string;
  amount_paid: string;
  balance_due: string;
  payments: PaymentOut[];
  created_at: string;
}

export function listTariffs(token: string) {
  return request<TariffOut[]>("/billing/tariffs", { token });
}

export function setTariff(token: string, payload: { category: string; item_name: string; unit_price: string }) {
  return request<TariffOut>("/billing/tariffs", { method: "PUT", token, body: payload });
}

export function listDiscountSchemes(token: string, includeInactive = false) {
  return request<DiscountSchemeOut[]>(`/billing/discount-schemes?include_inactive=${includeInactive}`, { token });
}

export function createDiscountScheme(
  token: string,
  payload: { name: string; discount_percent?: string; discount_amount?: string }
) {
  return request<DiscountSchemeOut>("/billing/discount-schemes", { method: "POST", token, body: payload });
}

export function deactivateDiscountScheme(token: string, schemeId: number) {
  return request<DiscountSchemeOut>(`/billing/discount-schemes/${schemeId}/deactivate`, { method: "POST", token });
}

export function openBill(
  token: string,
  payload: { patient_uhid: string; appointment_id?: number | null; admission_id?: number | null }
) {
  return request<BillOut>("/billing/bills", { method: "POST", token, body: payload });
}

export function getBill(token: string, billId: number) {
  return request<BillOut>(`/billing/bills/${billId}`, { token });
}

export function consolidateBill(token: string, billId: number) {
  return request<BillOut>(`/billing/bills/${billId}/consolidate`, { method: "POST", token });
}

export function addBillItem(token: string, billId: number, payload: { category: string; description: string; amount: string }) {
  return request<BillOut>(`/billing/bills/${billId}/items`, { method: "POST", token, body: payload });
}

export function applyDiscount(
  token: string,
  billId: number,
  payload: { scheme_id?: number; discount_percent?: string; discount_amount?: string; reason?: string }
) {
  return request<BillOut>(`/billing/bills/${billId}/discount`, { method: "POST", token, body: payload });
}

export function recordPayment(token: string, billId: number, payload: { amount: string; method: string }) {
  return request<BillOut>(`/billing/bills/${billId}/payments`, { method: "POST", token, body: payload });
}

// --- Staff accounts (US-19) & reports (US-20) ---------------------------------------------------

export interface StaffAccountOut {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  is_locked: boolean;
  created_at: string;
}

export function listStaff(token: string) {
  return request<StaffAccountOut[]>("/admin/staff", { token });
}

export function createStaff(token: string, payload: { username: string; password: string; role: string }) {
  return request<StaffAccountOut>("/admin/staff", { method: "POST", token, body: payload });
}

export function updateStaff(token: string, username: string, payload: { role?: string; is_active?: boolean }) {
  return request<StaffAccountOut>(`/admin/staff/${encodeURIComponent(username)}`, { method: "PATCH", token, body: payload });
}

export interface ReportSummary {
  start_date: string;
  end_date: string;
  opd_footfall: number;
  revenue: string;
  admissions_in_range: number;
  occupied_bed_days: number;
  available_bed_days: number;
  bed_occupancy_rate: number;
}

export function getReportSummary(token: string, startDate: string, endDate: string) {
  return request<ReportSummary>(`/admin/reports/summary?start_date=${startDate}&end_date=${endDate}`, { token });
}

/** Downloads need the bearer token, so fetch the file and hand the browser a blob. */
export async function fetchAuthorizedFile(token: string, path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new ApiError(response.status, response.statusText);
  return response.blob();
}
