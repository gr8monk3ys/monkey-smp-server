// One call to /auth/ (tools/staff_auth.py) or to the owner's /api/users. A refusal comes back as an AuthError whose
// message is the server's own sentence. (Not lib/api's call: a wrong password is a 401 here, which there means "your
// login ran out".)
export class AuthError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function auth<T = any>(method: string, path: string, body?: unknown, offline = "The page can't reach the server right now."): Promise<T> {
  const headers: Record<string, string> = { "X-Monkey-Staff": "1" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let answer: Response;
  try {
    answer = await fetch(path, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store", credentials: "same-origin",
    });
  } catch {
    throw new AuthError(offline, 0);
  }
  let data: any = null;
  try {
    data = await answer.json();
  } catch {
    data = null;
  }
  if (!answer.ok || !data || data.ok === false) {
    throw new AuthError((data && data.error) || `That didn't work (error ${answer.status}).`, answer.status);
  }
  return data as T;
}


/** The staff page's calls: the same, with the staff page's own words when the machine can't be reached. */
export const staffAuth = <T = any>(method: string, path: string, body?: unknown) =>
  auth<T>(method, path, body, "The page can't reach the server's machine right now.");

/** " 2 other sessions logged out.", or nothing when there were none. */
export const ended = (count?: number) => (count ? ` ${count} other session${count === 1 ? "" : "s"} logged out.` : "");

export const ROLES = ["moderator", "admin", "owner"] as const;
