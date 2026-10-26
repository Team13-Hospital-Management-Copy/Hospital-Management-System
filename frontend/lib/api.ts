const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
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
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    } catch {
      // body wasn't JSON; fall back to statusText
    }
    throw new ApiError(response.status, detail);
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
