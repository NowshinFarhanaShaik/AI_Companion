import { useId, type SelectHTMLAttributes } from "react";

type Props = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  options: { value: string; label: string }[];
  placeholder: string;
};

export function Select({ label, options, placeholder, className = "", id, ...rest }: Props) {
  const generated = useId();
  const selectId = id ?? generated;
  return (
    <div className="space-y-1">
      <label htmlFor={selectId} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <select
        id={selectId}
        {...rest}
        className={`w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50 disabled:text-slate-400 ${className}`}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
