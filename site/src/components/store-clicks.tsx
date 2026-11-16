"use client";

import { track } from "@vercel/analytics";
import { useEffect } from "react";

/** Counts clicks on any store link (every one carries data-link="STORE_URL") as a Vercel Analytics event, so the
 * visits-to-checkout step of the funnel shows up next to page views. */
export function StoreClicks() {
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const link = (event.target as Element | null)?.closest?.('a[data-link="STORE_URL"]');
      if (link) track("Store click", { page: location.pathname });
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);
  return null;
}
