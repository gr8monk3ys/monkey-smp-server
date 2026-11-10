import type { ReactNode } from "react";
import { Canopy, Footer } from "@/components/chrome";
import { GuideNav } from "@/components/guide-nav";
import { preloadMono } from "@/lib/fonts";
import "./guide.css";

/** Every guide page: the sidebar of pages on the left, the page you're reading on the right. */
export default function GuideLayout({ children }: { children: ReactNode }) {
  preloadMono(); // commands in the prose
  return (
    <>
      <Canopy here="guide" />

      <div className="docs">
        <GuideNav />
        <main id="main">{children}</main>
      </div>

      <Footer here="guide" />
    </>
  );
}
