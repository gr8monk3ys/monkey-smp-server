import { guideMetadata, GuidePage } from "@/components/guide-page";
import { FactionStandings } from "@/components/standings";
import StandingsNotes from "@/content/guide/standings.mdx";
import { builtPhase, config } from "@/lib/config";

export const metadata = guideMetadata("/guide/standings");

export default function StandingsPage() {
  return (
    <GuidePage href="/guide/standings"
      lede="Every faction gets a rank each week. Here is the table, and how a faction earns its points.">
      <FactionStandings url={config.STANDINGS_URL} launchAt={config.LAUNCH_AT} builtPhase={builtPhase()} />
      <div className="prose"><StandingsNotes /></div>
    </GuidePage>
  );
}
