import { guideMetadata, GuidePage } from "@/components/guide-page";
import DiscordGuide from "@/content/guide/discord.mdx";

export const metadata = guideMetadata("/guide/discord");

export default function DiscordPage() {
  return (
    <GuidePage href="/guide/discord">
      <div className="prose"><DiscordGuide /></div>
    </GuidePage>
  );
}
