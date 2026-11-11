import type { Metadata } from "next";
import { ChangeLine, Entry } from "@/components/changes";
import { Canopy, Footer } from "@/components/chrome";
import { Place } from "@/components/place";
import Changes from "@/content/changes.mdx";
import { preloadMono } from "@/lib/fonts";
import { CHANGES } from "@/lib/feed";
import { pageMetadata } from "@/lib/seo";
import "./changes.css";

const page = pageMetadata({ title: CHANGES.title, description: CHANGES.description, path: "/changes" });

// The feed is listed in the page's head too, so a feed reader given /changes finds it.
export const metadata: Metadata = {
  ...page,
  alternates: { ...page.alternates, types: { "application/rss+xml": [{ url: CHANGES.feed, title: CHANGES.title }] } },
};

export default function WhatChanged() {
  preloadMono(); // commands in the prose
  return (
    <>
      <Canopy here="changes" />

      <main id="main">
        <section className="hero">
          <h1>What changed</h1>
          <p className="lede">Announcements and every change to the rules, the mods and the wardrobe that you&apos;d
            notice in game, newest first. You don&apos;t need the Discord: what it announces goes here too.</p>
        </section>

        <section id="updates">
          <h2 className="visually-hidden">Updates</h2>
          <p className="small feed"><a href={CHANGES.feed}>Follow in a feed reader (RSS)</a></p>
          {/* The entries are src/content/changes.mdx. */}
          <Place className="changes">
            <Changes components={{ Entry, li: ChangeLine }} />
          </Place>
        </section>
      </main>

      <Footer here="changes" />
    </>
  );
}
