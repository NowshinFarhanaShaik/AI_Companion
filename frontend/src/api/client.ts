const BASE = `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/api`;
const ACCESS_KEY = "asc_access";
const REFRESH_KEY = "asc_refresh";

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export type Paginated<T> = { items: T[]; count: number };

type Params = Record<string, string | number | undefined>;
type Options = { body?: unknown; form?: FormData; params?: Params; blob?: boolean };

function messageFrom(data: unknown, status: number): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  // Validation errors arrive as a list of { loc, msg }.
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string; loc?: string[] };
    const field = first.loc?.[first.loc.length - 1];
    return field ? `${field}: ${first.msg}` : (first.msg ?? "Invalid input");
  }
  return status >= 500 ? "The server ran into a problem. Please try again in a moment." : `Request failed (${status})`;
}

// Shared so that parallel requests hitting a 401 trigger a single refresh.
let refreshing: Promise<boolean> | null = null;

function refreshAccess(): Promise<boolean> {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/token/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: tokens.refresh }),
    })
      .then(async (res) => {
        if (!res.ok) return false;
        tokens.set((await res.json()).access);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

async function request<T>(method: string, path: string, options: Options = {}, retry = true): Promise<T> {
  const url = new URL(BASE + path);
  for (const [key, value] of Object.entries(options.params ?? {})) {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
  }
  const headers: Record<string, string> = {};
  if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  let body: BodyInit | undefined;
  if (options.form) body = options.form;
  else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  let res: Response;
  try {
    res = await fetch(url, { method, headers, body });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection and try again.", 0, "network");
  }

  if (res.status === 401 && retry && tokens.refresh) {
    if (await refreshAccess()) return request<T>(method, path, options, false);
    tokens.clear();
    window.dispatchEvent(new Event("asc:logout"));
  }
  if (res.status === 204) return undefined as T;
  if (options.blob && res.ok) return (await res.blob()) as T;

  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(messageFrom(data, res.status), res.status, (data as { code?: string } | null)?.code);
  return data as T;
}

export const api = {
  get: <T>(path: string, params?: Params) => request<T>("GET", path, { params }),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, { body: body ?? {} }),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, { body: body ?? {} }),
  delete: <T>(path: string) => request<T>("DELETE", path),
  upload: <T>(path: string, form: FormData) => request<T>("POST", path, { form }),
  blob: (path: string) => request<Blob>("GET", path, { blob: true }),
};

/**
 * Opens a JWT-protected PDF in a new tab, optionally at a page. A plain link would get a 401.
 * The tab is opened before the first await because browsers block window.open after one.
 */
export async function openProtectedFile(path: string, page?: number): Promise<void> {
  const tab = window.open("", "_blank");
  try {
    const blob = await api.blob(path);
    const url = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
    const target = page ? `${url}#page=${page}` : url;
    if (tab) tab.location.href = target;
    else window.location.href = target;
    setTimeout(() => URL.revokeObjectURL(url), 5 * 60_000);
  } catch (error) {
    tab?.close();
    throw error;
  }
}
