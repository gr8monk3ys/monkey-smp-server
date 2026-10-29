import { guideMetadata, GuidePage } from "@/components/guide-page";
import Factions from "@/content/guide/factions.mdx";

export const metadata = guideMetadata("/guide/factions");

export default function FactionsPage() {
  return (
    <GuidePage href="/guide/factions">
      <div className="prose"><Factions /></div>
    </GuidePage>
  );
}
