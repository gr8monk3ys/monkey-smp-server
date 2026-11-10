import type { MDXComponents } from "mdx/types";
import { ConfigLink, LaunchTime } from "@/components/links";
import { Live, OffNote } from "@/components/live";

// The components every MDX file (src/content/*.mdx) can use without importing them:
//   <ConfigLink to="MAP_URL">live map</ConfigLink>               a link to one of config.json's URLs
//   <LaunchTime template="{date} at {pacific} ({eastern})" />   the season's launch, in words
//   <Live pack="monkey-drops">...</Live>                        only while that data pack runs (live-packs.json)
//   <OffNote packs={["monkey-drops"]} />                        "Not running on the server right now: ..."
const components: MDXComponents = { ConfigLink, LaunchTime, Live, OffNote };

export function useMDXComponents(given: MDXComponents = {}): MDXComponents {
  return { ...components, ...given };
}
