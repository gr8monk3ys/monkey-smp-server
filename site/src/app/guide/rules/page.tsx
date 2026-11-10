import { guideMetadata, GuidePage } from "@/components/guide-page";
import { OffNote } from "@/components/live";
import Rulebook from "@/content/guide/rulebook.mdx";

export const metadata = guideMetadata("/guide/rules");

export default function RulesPage() {
  // The rulebook is docs/RULES.md word for word, rules for every system included. The note, straight in the page,
  // says which of those systems aren't running now (tools/live_packs.py lets the whole page name them).
  return (
    <GuidePage href="/guide/rules">
      <OffNote packs={["monkey-rules", "monkey-standings", "monkey-events", "monkey-outposts", "monkey-sieges",
        "monkey-finale"]}>The rules about them apply when they run again.</OffNote>
      <div className="prose"><Rulebook /></div>
    </GuidePage>
  );
}
