import type { ReactNode } from "react";
import { Canopy, Footer } from "@/components/chrome";
import { GuideNav } from "@/components/guide-nav";
import { preloadMono } from "@/lib/fonts";
import "./guide.css";

/** Every guide page: the sidebar of pages on the left, the page you're reading on the right. Until the Season 1
 * guide is written, a notice says the pages describe Season I on the old modded server. */
export default function GuideLayout({ children }: { children: ReactNode }) {
  preloadMono(); // commands in the prose
  return (
    <>
      <Canopy here="guide" />

      <div className="docs">
        <GuideNav />
        <main id="main">
          <p className="notice">Monkey SMP relaunches as a free economy lifesteal server for Java and Bedrock with
            Season 1. These pages still describe Season I on the old modded server; the Season 1 guide replaces them
            before launch. <a href="/">What&apos;s new</a></p>
          {children}
        </main>
      </div>

      <Footer here="guide" />
    </>
  );
}
