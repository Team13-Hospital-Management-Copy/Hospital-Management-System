export function ErrorAlert({ message }: { message: string }) {
  return <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{message}</p>;
}

export function SuccessAlert({ children }: { children: React.ReactNode }) {
  return <div className="rounded-md bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{children}</div>;
}
