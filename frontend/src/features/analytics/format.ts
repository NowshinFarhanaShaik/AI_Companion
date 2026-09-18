export const percent = (value: number | null) => (value === null ? "—" : `${Math.round(value * 100)}%`);
export const usd = (value: number) => `$${value.toFixed(4)}`;
export const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
export const date = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString() : "—");
