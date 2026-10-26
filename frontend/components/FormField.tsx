import type { Accent } from "./Button";

const ACCENT_FOCUS: Record<Accent, string> = {
  teal: "focus:border-teal-600 focus:ring-teal-100",
  violet: "focus:border-violet-600 focus:ring-violet-100",
  rose: "focus:border-rose-600 focus:ring-rose-100",
};

interface FormFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
  min?: number;
  max?: number;
  placeholder?: string;
  mono?: boolean;
  accent?: Accent;
}

export function FormField({
  label,
  value,
  onChange,
  type = "text",
  required = false,
  min,
  max,
  placeholder,
  mono = false,
  accent = "teal",
}: FormFieldProps) {
  return (
    <div>
      <label className="block text-sm font-medium text-stone-700">{label}</label>
      <input
        type={type}
        required={required}
        min={min}
        max={max}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-900 shadow-sm transition focus:outline-none focus:ring-2 ${
          ACCENT_FOCUS[accent]
        } ${mono ? "font-mono" : ""}`}
      />
    </div>
  );
}
