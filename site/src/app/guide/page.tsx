import { guideMetadata, GuidePage } from "@/components/guide-page";
import { OldAnchors } from "@/components/old-anchors";
import FirstHour from "@/content/guide/first-hour.mdx";

export const metadata = guideMetadata("/guide");

export default function Guide() {
  return (
    <GuidePage href="/guide" lede={<>How Monkey SMP works, one page at a time. New here? Read this page and{" "}
      <a href="/guide/factions">Factions and land</a>. The rest is for when you need it.</>}>
      <OldAnchors />
      <div className="prose"><FirstHour /></div>
    </GuidePage>
  );
}
