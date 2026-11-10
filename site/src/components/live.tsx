import type { ReactNode } from "react";
import { notRunning, offText, type Pack, running } from "@/lib/live";

// Text tied to the server's own data packs (site/live-packs.json, src/lib/live.ts). MDX files get both without
// importing them (src/mdx-components.tsx).

/** Shown only while `pack` runs on the live server, or any of them when it is a list (`off` stands in for it
 * otherwise). */
export function Live({ pack, off, children }: { pack: Pack | Pack[]; off?: ReactNode; children: ReactNode }) {
  const packs = Array.isArray(pack) ? pack : [pack];
  return <>{packs.some(running) ? children : off}</>;
}

/** "Not running on the server right now: ..." for those of `packs` that aren't on; nothing when they all are.
 * Its data-off names them: tools/live_packs.py lets the note's parent element (the section it sits in) name those
 * packs' features, and nothing else on the page. */
export function OffNote({ packs, className = "small", as: Tag = "p", children }:
  { packs: Pack[]; className?: string; as?: "p" | "span"; children?: ReactNode }) {
  const off = notRunning(packs);
  if (!off.length) return null;
  return <Tag className={className} data-off={off.join(" ")}>{offText(off)}{children && <> {children}</>}</Tag>;
}
