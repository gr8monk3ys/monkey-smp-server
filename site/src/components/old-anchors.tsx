"use client";

import { useEffect } from "react";

// The guide used to be one long page; its sections are pages of their own now. A link to an old section
// (/guide#week, /guide#moderators) goes on to that section's page.
const MOVED: Record<string, string> = {
  "#factions": "/guide/factions",
  "#week": "/guide/week",
  "#commands": "/guide/commands",
  "#players": "/guide/commands/players",
  "#leaders": "/guide/commands/leaders",
  "#supporters": "/guide/commands/supporters",
  "#moderators": "/guide/commands/moderators",
  "#admins": "/guide/commands/admins",
};

export function OldAnchors() {
  useEffect(() => {
    const to = MOVED[window.location.hash];
    if (to) window.location.replace(to);
  }, []);
  return null;
}
