import { useId, type InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & { label?: string; error?: string };

export function Input({ label, error, className = "", id, ...rest }: Props) {
  const generated = useId();
  const inputId = id ?? generated;
  return (
    <div className="space-y-1">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-slate-700">
          {label}
        </label>
      )}
      <input
        id={inputId}
        {...rest}
        className={`w-full rounded-lg border px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 ${error ? "border-red-400" : "border-slate-300"} ${className}`}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
