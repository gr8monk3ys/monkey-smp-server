import type { ReactNode } from "react";
import { config, type LinkKey, sayLaunch, storeOpen, target } from "@/lib/config";

/** A link to one of config.json's URLs. data-link stays on it so tools/site_links.py --built can check the
 * built pages against config.json. */
export function ConfigLink({ to, className, download, children }:
  { to: LinkKey; className?: string; download?: boolean; children: ReactNode }) {
  const { href, title } = target(to);
  return (
    <a className={className} data-link={to} href={href} title={title} download={download || undefined}>
      {children}
    </a>
  );
}

/** The season's launch in words, from config.json's LAUNCH_AT: the template can say {date}, {pacific} and
 * {eastern}. */
export function LaunchTime({ template }: { template: string }) {
  return <time data-launch={template} dateTime={config.LAUNCH_AT}>{sayLaunch(template)}</time>;
}

/** Text that is true only once the store is open ("open"), or only until then ("soon"). */
export function Store({ when, children }: { when: "open" | "soon"; children: ReactNode }) {
  return (when === "open") === storeOpen ? <>{children}</> : null;
}
