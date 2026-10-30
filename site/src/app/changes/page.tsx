import type { Metadata } from "next";
import { ChangeLine, Entry } from "@/components/changes";
import { Canopy, Footer } from "@/components/chrome";
import { Place } from "@/components/place";
import Changes from "@/content/changes.mdx";
import { pageMetadata } from "@/lib/seo";
import "./changes.css";

export const metadata: Metadata = pageMetadata({
  title: "What changed: Monkey SMP patch notes",
  description: "Monkey SMP's patch notes: every change to the server's rules, mods, modpack and wardrobe that "
    + "players notice, newest first.",
  path: "/changes",
});

export default function WhatChanged() {
  return (
    <>
      <Canopy label="Site" items={[
        { label: "Join", href: "/#join" },
        { label: "Rules", href: "/#rules" },
        { label: "FAQ", href: "/#faq" },
        { label: "Guide", href: "/guide" },
      ]} />

      <main id="main">
        <section className="hero">
          <h1>What changed</h1>
          <p className="lede">Every change to the rules, the mods and the wardrobe that you&apos;d notice in game,
            newest first. The same notes go in the Discord&apos;s #changelog channel the day they go live.</p>
        </section>

        <section id="updates">
          <h2 className="visually-hidden">Updates</h2>
          {/* The entries are src/content/changes.mdx. */}
          <Place className="changes">
            <Changes components={{ Entry, li: ChangeLine }} />
          </Place>
        </section>
      </main>

      <Footer items={[
        { label: "Monkey SMP", href: "/" },
        { label: "Discord", to: "DISCORD_INVITE" },
        { label: "Rules", href: "/#rules" },
        { label: "Live map", to: "MAP_URL" },
        { label: "How it works", href: "/guide" },
      ]} />
    </>
  );
}
