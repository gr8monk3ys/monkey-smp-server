// Asking the root helper (backups, restores, version switch, world reset and swap) and waiting for its answer.
// The page posts the request; the helper picks it up within seconds; the page reads /api/helper until the job
// is no longer "running" (about 5 minutes at most). The jobs list in the Backups box sees every poll.
import { useEffect, useRef } from "react";
import { get, post } from "../../lib/api";
import type { Messages } from "../../lib/hooks";

const HELPER_POLL_MS = 3_000;
const HELPER_POLL_MAX = 100;     // about 5 minutes
const HELPER_POLL_TRIES = 3;     // a failed poll is tried this many times before it counts as an error
const HELPER_BAD = ["failed", "refused", "stopped"];

export interface Job {
  id: string;
  action: string;
  state: string;
  time: unknown;
  message: string;
}

const sleep = (ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms));

const feed = new EventTarget();
/** Tell the jobs list what the helper answered. */
export const publishJobs = (data: { jobs?: Job[] }) => feed.dispatchEvent(new CustomEvent("jobs", { detail: data }));

/** Listen for the helper's answers while mounted. */
export function useJobFeed(handler: (data: { jobs?: Job[] }) => void) {
  const latest = useRef(handler);
  useEffect(() => {
    latest.current = handler;
  });
  useEffect(() => {
    const listener = (event: Event) => latest.current((event as CustomEvent).detail);
    feed.addEventListener("jobs", listener);
    return () => feed.removeEventListener("jobs", listener);
  }, []);
}

/** A function that says whether the component is still on the page (a wait ends when it leaves). */
export function useAlive(): () => boolean {
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  return () => alive.current;
}

async function waitFor(request: string, alive: () => boolean): Promise<Job | null> {
  for (let i = 0; i < HELPER_POLL_MAX; i += 1) {
    await sleep(HELPER_POLL_MS);
    if (!alive()) return null;
    let data: { jobs?: Job[] } | null = null;
    for (let attempt = 0; attempt < HELPER_POLL_TRIES && !data; attempt += 1) {
      try {
        data = await get("/api/helper");
      } catch (error) {
        if (attempt === HELPER_POLL_TRIES - 1) throw error;
        await sleep(HELPER_POLL_MS);
      }
    }
    if (!data) return null;
    publishJobs(data);
    const job = (data.jobs || []).find((j) => j.id === request);
    if (job && job.state !== "running") return job;
  }
  return null;
}

/** Asks the root helper for a job and waits for its result, which goes in the box's messages. */
export async function askHelper(url: string, body: unknown, words: string, m: Messages, alive: () => boolean): Promise<Job | null> {
  m.clear();
  try {
    const done = await post(url, body || {});
    m.say(`${words} The helper picks it up in a few seconds.`);
    const job = await waitFor(done.request, alive);
    if (!alive()) return job;
    if (job) {
      m.clear();
      if (HELPER_BAD.includes(job.state)) m.setError(job.message);
      else m.say(job.message);
    } else m.say("Still running: see the jobs list.");
    return job;
  } catch (error) {
    m.fail(error);
    return null;
  }
}
