import type { Metadata } from "next";
import { LegalPage } from "@/components/legal-page";
import Privacy from "@/content/legal/privacy.mdx";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Privacy policy · Monkey SMP",
  description: "What Monkey SMP's website, Minecraft server, store and Discord record about you, why, how long it "
    + "is kept, who else handles it and how to see or delete it.",
  path: "/privacy",
});

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy policy" updated="2026-11-09"
      lede="What we record when you visit this site, play on the server or buy a pass, why we record it, how long we
        keep it and how to see it or have it deleted.">
      <Privacy />
    </LegalPage>
  );
}
