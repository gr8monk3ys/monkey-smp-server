// What one tab tells another (the old page used window events for the same):
//   open-file        {path, writable}  Mod settings -> Files: open this file in the raw editor
//   run-command      {command}         a saved command -> Console: send it as if typed
//   players-changed  {}                something changed a player list -> Players reloads
//   changed          {}                anything was changed -> the record of changes reloads
import { useEffect, useRef } from "react";

export type BusEvents = {
  "open-file": { path: string; writable?: boolean };
  "run-command": { command: string };
  "players-changed": Record<string, never>;
  changed: Record<string, never>;
};

const target = new EventTarget();

export function emit<K extends keyof BusEvents>(name: K, detail: BusEvents[K]) {
  target.dispatchEvent(new CustomEvent(name, { detail }));
}

/** Listen while mounted. The handler may change on each render; the latest one is called. */
export function useBus<K extends keyof BusEvents>(name: K, handler: (detail: BusEvents[K]) => void) {
  const latest = useRef(handler);
  useEffect(() => {
    latest.current = handler;
  });
  useEffect(() => {
    const listener = (event: Event) => latest.current((event as CustomEvent<BusEvents[K]>).detail);
    target.addEventListener(name, listener);
    return () => target.removeEventListener(name, listener);
  }, [name]);
}

/** Tell the others something changed (the record of changes reads itself again). */
export const changed = () => emit("changed", {});
