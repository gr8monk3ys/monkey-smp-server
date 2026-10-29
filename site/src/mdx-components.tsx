import type { MDXComponents } from "mdx/types";
import { ConfigLink, LaunchTime } from "@/components/links";

// The components every MDX file (src/content/*.mdx) can use without importing them:
//   <ConfigLink to="MAP_URL">live map</ConfigLink>               a link to one of config.json's URLs
//   <LaunchTime template="{date} at {pacific} ({eastern})" />   the season's launch, in words
const components: MDXComponents = { ConfigLink, LaunchTime };

export function useMDXComponents(given: MDXComponents = {}): MDXComponents {
  return { ...components, ...given };
}
