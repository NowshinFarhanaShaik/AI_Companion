import type { ReactNode } from "react";

export type Column<T> = { header: string; cell: (row: T) => ReactNode; numeric?: boolean };

type Props<T> = { columns: Column<T>[]; rows: T[]; rowKey: (row: T) => string; empty?: string };

export function SimpleTable<T>({ columns, rows, rowKey, empty = "Nothing to show yet." }: Props<T>) {
  if (rows.length === 0) return <p className="text-sm text-slate-600">{empty}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-slate-500">
            {columns.map((column) => (
              <th
                key={column.header}
                scope="col"
                className={`px-3 py-2 font-medium ${column.numeric ? "text-right" : "text-left"}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-b border-slate-100">
              {columns.map((column) => (
                <td
                  key={column.header}
                  className={`px-3 py-2 ${column.numeric ? "text-right tabular-nums" : ""} text-slate-800`}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
