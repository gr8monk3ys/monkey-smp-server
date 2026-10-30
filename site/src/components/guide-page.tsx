import type { Metadata } from "next";
import type { ReactNode } from "react";
import { JsonLd } from "@/components/json-ld";
import { guidePage, pages } from "@/content/guide/pages";
import { guideTrail, pageMetadata } from "@/lib/seo";

/** The title and description a guide page gives search engines and link previews. */
export function guideMetadata(href: string): Metadata {
  const page = guidePage(href);
  return pageMetadata({ title: `${page.title} · Monkey SMP guide`, description: page.description, path: href });
}

/** One page of the guide: its title, an optional lede, the page itself, then the pages before and after it. */
export function GuidePage({ href, lede, children }: { href: string; lede?: ReactNode; children: ReactNode }) {
  const page = guidePage(href);
  const at = pages.indexOf(page);
  const prev = pages[at - 1];
  const next = pages[at + 1];
  return (
    <article className="doc">
      <JsonLd data={guideTrail(page.title, page.href)} />
      <h1>{page.title}</h1>
      {lede && <p className="lede">{lede}</p>}
      {children}
      <nav className="pager" aria-label="Previous and next">
        {prev && <a className="prev" href={prev.href}><span>Previous</span>{prev.title}</a>}
        {next && <a className="next" href={next.href}><span>Next</span>{next.title}</a>}
      </nav>
    </article>
  );
}
