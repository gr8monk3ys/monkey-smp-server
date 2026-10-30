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
      <Canopy label="Site" items={[
        { label: "Join", href: "/#join" },
        { label: "Rules", href: "/#rules" },
        { label: "Commands", href: "/guide/commands/players" },
        { label: "Discord", to: "DISCORD_INVITE" },
      ]} />

      <div className="docs">
        <GuideNav />
        <main id="main">{children}</main>
      </div>

      <Footer items={[
        { label: "Monkey SMP", href: "/" },
        { label: "Discord", to: "DISCORD_INVITE" },
        { label: "Rules", href: "/#rules" },
        { label: "Live map", to: "MAP_URL" },
        { label: "What changed", href: "/changes" },
      ]} />
    </>
  );
}
