import type { TabProps } from "../../shell/tabs";
import { PageHead, Panels } from "../../ui/kit";
import IpBans from "./IpBans";
import KnownPlayers from "./Known";
import { BlockHistory, PlayerHistory } from "./Lookup";
import Roster from "./Roster";
import TempBans from "./TempBans";

// The player list is the hero: who is on now, with the buttons for each, then the lists, then the look-ups.
export default function PlayersTab({ active }: TabProps) {
  return (
    <>
      <PageHead title="Players">
        <p>These buttons type the console command for you. Names are 3 to 16 letters, digits or underscores.</p>
      </PageHead>
      <Roster active={active} />
      <Panels className="mt-4">
        <TempBans active={active} />
        <IpBans active={active} />
        <KnownPlayers active={active} />
        <PlayerHistory />
        <BlockHistory />
      </Panels>
    </>
  );
}
