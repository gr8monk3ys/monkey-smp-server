import { guideMetadata, GuidePage } from "@/components/guide-page";
import Rulebook from "@/content/guide/rulebook.mdx";

export const metadata = guideMetadata("/guide/rules");

export default function RulesPage() {
  return (
    <GuidePage href="/guide/rules">
      <div className="prose"><Rulebook /></div>
    </GuidePage>
  );
}
