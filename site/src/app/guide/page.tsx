import type { Metadata } from "next";
import { GuidePage } from "@/components/guide-page";
import { OldAnchors } from "@/components/old-anchors";
import { ServerStatus } from "@/components/status";
import FirstHour from "@/content/guide/first-hour.mdx";
import { builtPhase, config } from "@/lib/config";
import { pageMetadata } from "@/lib/seo";

// /guide is the address every nav and footer links as the guide, so its preview describes the whole guide, not
// just this first page.
export const metadata: Metadata = pageMetadata({
  title: "Player guide: how Monkey SMP works",
  description: "How the Monkey SMP factions server works: the first hour, factions and land claims, a week of "
    + "challenges, drops and events, and every command by rank, from player to admin.",
  path: "/guide",
});

export default function Guide() {
  return (
    <GuidePage href="/guide" lede={<>How Monkey SMP works, one page at a time. New here? Read this page and{" "}
      <a href="/guide/factions">Factions and land</a>. The rest is for when you need it.</>}>
      <OldAnchors />
      {config.STATUS_URL && <ServerStatus line url={config.STATUS_URL} mapUrl={config.MAP_URL}
        launchAt={config.LAUNCH_AT} builtPhase={builtPhase()} />}
      <div className="prose"><FirstHour /></div>
    </GuidePage>
  );
}
