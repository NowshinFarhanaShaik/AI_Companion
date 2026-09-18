// The table view behind every chart, so no value is reachable only by hovering.
export function ChartDataTable({ headers, rows }: { headers: [string, string]; rows: [string, string][] }) {
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-slate-600">Show as a table</summary>
      <table className="mt-2 w-full text-left">
        <thead className="text-slate-500">
          <tr>
            <th className="py-1 font-medium">{headers[0]}</th>
            <th className="py-1 text-right font-medium">{headers[1]}</th>
          </tr>
        </thead>
        <tbody className="tabular-nums text-slate-800">
          {rows.map(([label, value], index) => (
            <tr key={index} className="border-t border-slate-100">
              <td className="py-1">{label}</td>
              <td className="py-1 text-right">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
