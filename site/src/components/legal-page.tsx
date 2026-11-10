import type { ReactNode } from "react";
import { Canopy, Footer } from "@/components/chrome";
import { dayLabel } from "@/lib/config";
import "@/app/guide/guide.css";

/** A legal page (/privacy, /terms): its title, what it is in a sentence, the day it last changed, then the prose
 * (src/content/legal/*.mdx) at the guide's reading width. `updated` is '2026-11-09'. */
export function LegalPage({ title, lede, updated, children }:
  { title: string; lede: ReactNode; updated: string; children: ReactNode }) {
  return (
    <>
      <Canopy />

      <main id="main">
        <section className="hero">
          <h1>{title}</h1>
          <p className="lede">{lede}</p>
          <p className="small">Last updated <time dateTime={updated}>{dayLabel(updated)}</time>.</p>
        </section>

        <section className="doc">
          <div className="prose">{children}</div>
        </section>
      </main>

      <Footer />
    </>
  );
}
