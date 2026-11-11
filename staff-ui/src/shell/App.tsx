// The staff page's frame: the header (with the server's status word on every tab and the account menu), the tabs
// (a rail on a wide screen, a sideways-scrolling row on a phone) and the open tab. The hash says which tab is open
// (#players), as the old page did, so links and the back button keep working.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, ClipboardList, FolderOpen, KeyRound, Puzzle, ScrollText, Server, SlidersHorizontal, Terminal, UsersRound,
  type LucideIcon,
} from "lucide-react";
import { get } from "../lib/api";
import { roleAtLeast, SessionProvider, useSession as useSessionLike, type Me, type Role } from "../lib/session";
import { currentVerdict, StatusProvider, useStatus, agoMs } from "../lib/status";
import { cx, Mark } from "../ui/kit";
import { Account } from "./Account";
import { TABS } from "./tabs";

const ICONS: Record<string, LucideIcon> = {
  status: Activity, players: UsersRound, console: Terminal, reports: ClipboardList, server: Server,
  settings: SlidersHorizontal, mods: Puzzle, modcfg: ScrollText, files: FolderOpen, users: KeyRound,
};

const CLOCK = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });

function useHashTab(ids: string[]) {
  const read = useCallback(() => {
    const wanted = location.hash.slice(1);
    return ids.includes(wanted) ? wanted : "status";
  }, [ids]);
  const [tab, setTab] = useState(read);
  useEffect(() => {
    const on = () => setTab(read());
    window.addEventListener("hashchange", on);
    on();
    return () => window.removeEventListener("hashchange", on);
  }, [read]);
  return tab;
}

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [meError, setMeError] = useState(false);
  const loadMe = useCallback(() => {
    get<Me>("/api/me").then((m) => {
      setMe(m);
      setMeError(false);
    }, () => setMeError(true));
  }, []);
  useEffect(loadMe, [loadMe]);
  const session = useMemo(() => ({ me, can: (need: Role) => roleAtLeast(me?.role, need), refresh: loadMe }), [me, loadMe]);

  return (
    <SessionProvider value={session}>
      <StatusProvider>
        <Frame meError={meError} />
      </StatusProvider>
    </SessionProvider>
  );
}

function Frame({ meError }: { meError: boolean }) {
  const { me } = useSessionLike();
  const visible = useMemo(() => TABS.filter((t) => !t.need || roleAtLeast(me?.role, t.need)), [me]);
  const ids = useMemo(() => visible.map((t) => t.id), [visible]);
  const current = useHashTab(ids);
  // A tab stays mounted once opened: an open file, a typed command or a search survives a look elsewhere.
  const [opened, setOpened] = useState<Set<string>>(() => new Set([current]));
  useEffect(() => setOpened((s) => (s.has(current) ? s : new Set(s).add(current))), [current]);
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    window.scrollTo({ top: 0 });
  }, [current]);

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[15rem_minmax(0,1fr)] lg:bg-[linear-gradient(to_right,var(--color-shade)_15rem,transparent_15rem)]">
      <a href="#main" className="btn btn-primary fixed left-3 top-3 z-50 -translate-y-24 focus:translate-y-0">Skip to content</a>
      <Rail tabs={visible} current={current} />
      <div className="min-w-0">
        <TopBar tabs={visible} current={current} />
        <main id="main" ref={main} tabIndex={-1} className="mx-auto w-full max-w-[84rem] px-4 pb-16 pt-6 outline-none sm:px-6 lg:px-10 lg:pt-8">
          {meError && (
            <p className="msg msg-error mb-4" role="alert">
              The page couldn't ask who you are, so buttons that need a role stay off. Reload to try again.
            </p>
          )}
          {visible.map((t) =>
            opened.has(t.id) ? (
              <div key={t.id} hidden={t.id !== current} id={`tab-${t.id}`}>
                <t.component active={t.id === current} />
              </div>
            ) : null,
          )}
        </main>
        {current === "status" && (
          <footer className="mx-auto max-w-[84rem] px-4 pb-10 sm:px-6 lg:px-10">
            <p className="fine border-t-2 border-leaf-2 pt-4">
              Look, don't touch: nothing on this tab can change the server. The other tabs can, and every change is
              logged with your name. Please keep the address and your password to yourself.
            </p>
          </footer>
        )}
      </div>
    </div>
  );
}

function Brand({ className }: { className?: string }) {
  return (
    <a href="#status" aria-label="Monkey SMP staff" className={cx("flex shrink-0 items-center gap-2.5 text-bone no-underline hover:text-bone", className)}>
      <img src="/img/monkey.svg" alt="" width={32} height={32} className="pixelated size-8 shrink-0" />
      {/* On a phone the mark alone: the row has the status word and the account menu to fit. */}
      <span className="hidden font-display text-xl leading-none sm:inline">
        Monkey <span className="text-gold">SMP</span> <span className="text-sage">staff</span>
      </span>
    </a>
  );
}

/** The status word and its mark, linked to the Status tab, in the header of every tab. */
function Pulse() {
  const status = useStatus();
  const v = currentVerdict(status);
  useEffect(() => {
    document.title = v ? `${v.word}: Monkey SMP staff` : "Monkey SMP staff";
  }, [v?.word]); // eslint-disable-line react-hooks/exhaustive-deps
  const checked = status.data ? new Date(status.data.checked) : null;
  return (
    <a href="#status" className="frame-shade flex min-h-11 min-w-0 items-center gap-2.5 px-2 py-1 text-bone no-underline hover:text-bone" aria-live="polite">
      <span className="sr-only">Server: </span>
      <Mark kind={v?.kind ?? "unknown"} className="size-3.5" />
      <span className="min-w-0 truncate font-bold">{v?.word ?? "Checking"}</span>
      {checked && (
        <span className="meta hidden truncate sm:inline">
          checked {agoMs(status.now - checked.getTime())}, {CLOCK.format(checked)}
        </span>
      )}
    </a>
  );
}

function TopBar({ tabs, current }: { tabs: typeof TABS; current: string }) {
  return (
    <div className="sticky top-0 z-30 bg-leaf-2">
      <header className="flex items-center gap-2 px-4 py-2.5 sm:gap-3 sm:px-6 lg:px-10">
        <Brand className="lg:hidden" />
        <div className="ml-auto flex min-w-0 items-center gap-2 lg:ml-0">
          <Pulse />
        </div>
        <div className="ml-auto hidden lg:block" />
        <Account />
      </header>
      <PhoneTabs tabs={tabs} current={current} />
      <div className="canopy" aria-hidden="true" />
    </div>
  );
}

/** On a phone: one row of tabs that scrolls sideways, the open one kept in view. */
function PhoneTabs({ tabs, current }: { tabs: typeof TABS; current: string }) {
  const row = useRef<HTMLElement>(null);
  useEffect(() => {
    const nav = row.current;
    const a = nav?.querySelector<HTMLElement>('[aria-current="page"]');
    if (!nav || !a) return;
    // Only the row moves: scrollIntoView would move the page too.
    const r = nav.getBoundingClientRect();
    const b = a.getBoundingClientRect();
    if (b.left < r.left) nav.scrollLeft -= r.left - b.left + 16;
    else if (b.right > r.right) nav.scrollLeft += b.right - r.right + 16;
  }, [current, tabs.length]);
  return (
    <nav ref={row} aria-label="Sections" className="flex gap-1 overflow-x-auto px-2 [scrollbar-width:none] lg:hidden">
      {tabs.map((t) => (
        <a
          key={t.id}
          href={`#${t.id}`}
          aria-current={t.id === current ? "page" : undefined}
          className={cx(
            "shrink-0 whitespace-nowrap border-b-4 px-3 pb-2 pt-1 font-bold no-underline",
            t.id === current ? "border-bone text-bone" : "border-transparent text-sage hover:text-bone",
          )}
        >
          {t.label}
        </a>
      ))}
    </nav>
  );
}

/** On a wide screen: the tabs in a rail on the left, grouped by job. */
function Rail({ tabs, current }: { tabs: typeof TABS; current: string }) {
  const groups = ["Watching", "Running", "Owner"] as const;
  return (
    <aside className="sticky top-0 hidden h-dvh flex-col gap-6 overflow-y-auto bg-shade px-4 py-5 lg:flex">
      <Brand />
      <nav aria-label="Sections" className="flex flex-col gap-5">
        {groups.map((g) => {
          const mine = tabs.filter((t) => t.group === g);
          if (!mine.length) return null;
          return (
            <div key={g}>
              <p className="mb-1.5 px-2 text-sm text-sage">{g}</p>
              <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
                {mine.map((t) => {
                  const Icon = ICONS[t.id];
                  const on = t.id === current;
                  return (
                    <li key={t.id}>
                      <a
                        href={`#${t.id}`}
                        aria-current={on ? "page" : undefined}
                        className={cx(
                          "flex min-h-11 items-center gap-3 px-2 font-bold no-underline",
                          on ? "frame-gold -mx-1.5 text-ink hover:text-ink" : "text-bone-2 hover:bg-leaf hover:text-bone",
                        )}
                      >
                        {Icon && <Icon aria-hidden="true" className="size-[18px] shrink-0" strokeWidth={2.25} />}
                        {t.label}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>
      <p className="mt-auto px-2 text-xs text-hint">Every change here is logged with your name.</p>
    </aside>
  );
}
