import type { Metadata } from "next";
import { GuidePage } from "@/components/guide-page";
import { OldAnchors } from "@/components/old-anchors";
import FirstHour from "@/content/guide/first-hour.mdx";

// /guide is the address every nav and footer links as the guide, so its preview describes the whole guide, not
// just this first page.
export const metadata: Metadata = {
  title: "How it works - Monkey SMP",
  description: "How Monkey SMP works: the first hour, factions and land, a week of challenges, drops and events, "
    + "and every command by rank, from player to admin.",
};

export default function Guide() {
  return (
    <GuidePage href="/guide" lede={<>How Monkey SMP works, one page at a time. New here? Read this page and{" "}
      <a href="/guide/factions">Factions and land</a>. The rest is for when you need it.</>}>
      <OldAnchors />
      <div className="prose"><FirstHour /></div>
    </GuidePage>
  );
}
