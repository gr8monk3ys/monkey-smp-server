// What the parts of the Mods tab share: one box of messages, the typed step, the question "do players need it?", and
// a way to read the mods again.
import { createContext, useContext } from "react";
import { when } from "../../lib/format";
import type { Messages } from "../../lib/hooks";
import type { StepSpec } from "./step";

export interface ModCtl {
  m: Messages;
  /** Open the typed step: the jar's file name is the word to type. */
  step: (message: string, yes: string, file: string, onYes: (ticked: boolean) => void, check?: { label: string; checked: boolean }, danger?: boolean) => void;
  openStep: (spec: StepSpec) => void;
  /** A call that changes one jar: POST, then say what happened. */
  call: (url: string, body: unknown, words: string) => Promise<void>;
  /** The change is made: say so, and what players need. */
  done: (text: string, done: any) => void;
  askPlayers: (file: string, failed: boolean) => void;
  reload: () => void;
}

export const ModsContext = createContext<ModCtl>(null as unknown as ModCtl);
export const useMods = () => useContext(ModsContext);

export const PINNED_NOTE = " It is one of this release's pinned mods, so the server puts the pinned jar back when it next starts.";
export const HELD_NOTE = " It is one of this release's pinned mods and stays off after restarts until someone presses Allow again.";
export const KEEP_OFF = { label: "Keep it off after restarts", checked: true };

/** What the page says about a mod players need, from in_players_pack: false (checked, not there), true, or null
 * (the players' pack couldn't be read here). */
export function playersNeed(done: any): string {
  if (done.client_side !== "required") return "";
  if (done.in_players_pack === false) {
    return "Players must install this too. It is not in the players' pack yet, so they may not be able to join until the owner adds it.";
  }
  if (done.in_players_pack === true) return "";
  return "Players need this mod too. The players' pack couldn't be read here, so check that it has it.";
}

export const heldWords = (h: any) => (h ? `kept off by ${h.by || "staff"}${h.at ? ` since ${when(h.at)}` : ""}` : "");

// tools/staff_host.py, MOD_NAME
export const JAR_NAME = /^(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9 ._+()-]{0,123}\.jar$/;
export const PACK_NAME = /^[A-Za-z0-9][A-Za-z0-9 ._+()-]{0,123}\.mrpack$/;
export const DATAPACK_NAME = /^[A-Za-z0-9][A-Za-z0-9._+-]{0,123}\.zip$/;
