/** Structured data for search engines (src/lib/seo.ts), as a JSON-LD script. "<" is escaped so no string in it
 * can close the script early. */
export function JsonLd({ data }: { data: object }) {
  return (
    <script type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }} />
  );
}
