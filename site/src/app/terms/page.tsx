import type { Metadata } from "next";
import { LegalPage } from "@/components/legal-page";
import Terms from "@/content/legal/terms.mdx";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Terms of service · Monkey SMP",
  description: "The terms for playing on Monkey SMP and buying a Server Pass or supporter tier: who can play, "
    + "payments, renewals and refunds, the rules, seasons and what we can't promise.",
  path: "/terms",
});

export default function TermsPage() {
  return (
    <LegalPage title="Terms of service" updated="2026-11-09"
      lede="The agreement between you and Monkey SMP when you use this site, play on the server or buy a pass. The
        rulebook says how to play; this page covers the rest.">
      <Terms />
    </LegalPage>
  );
}
