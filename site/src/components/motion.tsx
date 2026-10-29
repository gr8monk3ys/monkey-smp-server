"use client";

import { MotionConfig } from "framer-motion";
import type { ReactNode } from "react";

/** Any framer-motion animation on the site follows the visitor's reduced-motion setting. The site's own motion
 * is CSS (steps() only, DESIGN.md) and is switched off in style.css under prefers-reduced-motion. */
export function Motion({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
