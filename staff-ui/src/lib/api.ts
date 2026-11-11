// One call to the panel (tools/staff_panel.py) or the login (tools/staff_auth.py). Every request carries the page's
// own `X-Monkey-Staff: 1` header: the panel refuses a change without it. A failure comes back as an ApiError whose
// message is a sentence for the page, as the old panel.js did.

export class ApiError extends Error {
  status: number;
  data: any;
  constructor(message: string, status: number, data: any = null) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export type Body = unknown;

export interface CallOptions {
  /** Raw bytes sent as application/octet-stream (uploads). */
  raw?: Blob | ArrayBuffer;
  signal?: AbortSignal;
  /** Extra headers, e.g. X-File-Name for an upload. */
  headers?: Record<string, string>;
}

export async function api<T = any>(method: string, url: string, body?: Body, options: CallOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "X-Monkey-Staff": "1", ...options.headers };
  let payload: BodyInit | undefined;
  if (options.raw !== undefined) {
    headers["Content-Type"] = "application/octet-stream";
    payload = options.raw;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let answer: Response;
  try {
    answer = await fetch(url, { method, headers, body: payload, cache: "no-store", signal: options.signal });
  } catch (error) {
    if ((error as Error)?.name === "AbortError") throw error;
    throw new ApiError("The page can't reach the server's machine right now.", 0);
  }
  let data: any = null;
  try {
    data = await answer.json();
  } catch {
    data = null;
  }
  if (answer.status === 401) throw new ApiError("Your login has run out. Reload this page to log in again.", 401, data);
  if (!answer.ok || (data && data.ok === false)) {
    throw new ApiError((data && data.error) || `That didn't work (error ${answer.status}).`, answer.status, data);
  }
  return (data || {}) as T;
}

export const get = <T = any>(url: string, signal?: AbortSignal) => api<T>("GET", url, undefined, { signal });
export const post = <T = any>(url: string, body?: Body) => api<T>("POST", url, body ?? {});

export const query = (params: Record<string, string | number | boolean | undefined | null>) =>
  new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => [k, String(v)]),
  ).toString();

/** A list out of an answer that is either the list or holds it under `key`. */
export const listOf = <T = any>(data: any, key: string): T[] =>
  Array.isArray(data?.[key]) ? data[key] : Array.isArray(data) ? data : [];

export const messageOf = (error: unknown) =>
  error instanceof Error ? error.message : error ? String(error) : "";
