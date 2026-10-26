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
}: FormFieldProps) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700">{label}</label>
      <input
        type={type}
        required={required}
        min={min}
        max={max}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm transition focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100 ${
          mono ? "font-mono" : ""
        }`}
      />
    </div>
  );
}
