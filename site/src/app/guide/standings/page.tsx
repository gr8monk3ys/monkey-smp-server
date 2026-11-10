import { guideMetadata, GuidePage } from "@/components/guide-page";
import { OffNote } from "@/components/live";
import { FactionStandings } from "@/components/standings";
import StandingsNotes from "@/content/guide/standings.mdx";
import { builtPhase, config } from "@/lib/config";
import { running } from "@/lib/live";

export const metadata = guideMetadata("/guide/standings");

export default function StandingsPage() {
  // While the standings pack isn't running (site/live-packs.json) the page says so and shows nothing else.
  if (!running("monkey-standings")) {
    return <GuidePage href="/guide/standings"><OffNote packs={["monkey-standings"]} className="lede" /></GuidePage>;
  }
  return (
    <GuidePage href="/guide/standings"
      lede="Every faction gets a rank each week. Here is the table, and how a faction earns its points.">
      <FactionStandings url={config.STANDINGS_URL} launchAt={config.LAUNCH_AT} builtPhase={builtPhase()} />
      <div className="prose"><StandingsNotes /></div>
    </GuidePage>
  );
}
