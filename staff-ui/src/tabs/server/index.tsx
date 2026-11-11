// Server: power first, then backups, the world, the release, Java, timed jobs, the lag finder and the record of changes.
import type { TabProps } from "../../shell/tabs";
import { PageHead, Panels } from "../../ui/kit";
import Activity from "./Activity";
import Events from "./Events";
import Helper from "./Helper";
import Lag from "./Lag";
import { Java, Sftp, Version } from "./Machine";
import { LastBackup, Power } from "./Power";
import { Schedules, Timers } from "./Schedules";
import { Download, Reset, Upload } from "./World";

export default function ServerTab({ active }: TabProps) {
  return (
    <>
      <PageHead title="Server">
        <p>Power, backups, the world, versions and timed jobs. A big step asks you to type a word to confirm it.</p>
      </PageHead>
      <Panels>
        <Power active={active} />
        <LastBackup active={active} />
        <Events active={active} />
        <Helper active={active} />
        <Download />
        <Version active={active} />
        <Java active={active} />
        <Reset />
        <Upload active={active} />
        <Sftp active={active} />
        <Timers active={active} />
        <Schedules active={active} />
        <Lag active={active} />
        <Activity active={active} />
      </Panels>
    </>
  );
}
