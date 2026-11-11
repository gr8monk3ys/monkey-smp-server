// The server's own folder: browse, open, edit, save, upload, download, rename and delete (tools/staff_panel.py answers
// /api/files and friends). Every change is kept in history. The tab stays mounted, so an open file survives a look
// at another tab.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, get, listOf, post, query } from "../../lib/api";
import { useBus } from "../../lib/bus";
import { size, when } from "../../lib/format";
import { useMessages, useOnShow } from "../../lib/hooks";
import type { TabProps } from "../../shell/tabs";
import { Actions, Button, Empty, Input, Messages, PageHead, Panel, Panels, Rows, Row, Textarea, useConfirm } from "../../ui/kit";
import History from "./History";
import Search from "./Search";

const MAX_UPLOAD = 64 * 1048576;
const FILE_NAME = /^[A-Za-z0-9._+-]+$/;

interface Entry {
  name: string;
  dir?: boolean;
  size?: number;
  mtime?: unknown;
  writable?: boolean;
}

interface OpenFile {
  path: string;
  mtime: unknown;
  writable: boolean;
  text: string;
  size: number;
}

const join = (dir: string, name: string) => (dir ? `${dir}/${name}` : name);
const downloadUrl = (path: string) => `/api/download?${query({ path })}`;

export default function FilesTab({ active }: TabProps) {
  const m = useMessages();
  const { fail, say, clear, setError } = m;
  const [confirm, ask] = useConfirm();
  const [dir, setDir] = useState("");
  const [writableDir, setWritableDir] = useState(true);
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [filter, setFilter] = useState("");
  const [file, setFile] = useState<OpenFile | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [offer, setOffer] = useState(""); // a file the editor won't open, but that can be downloaded
  const [changes, setChanges] = useState(0); // counts changes, so an open history reads itself again
  const dirRef = useRef("");
  const opening = useRef(false); // a file is open or being opened: a tab visit must not close it
  const picker = useRef<HTMLInputElement>(null);

  const dirty = Boolean(file && file.writable && draft !== file.text);

  const loadDir = useCallback(
    async (to: string, force = true) => {
      setError("");
      setOffer("");
      try {
        const data = await get(`/api/files?${query({ path: to })}`);
        if (!force && opening.current) return;
        const path = data.path === undefined ? to : data.path;
        dirRef.current = path;
        setDir(path);
        setWritableDir(data.writable !== false);
        setFile(null);
        opening.current = false;
        setEntries(listOf<Entry>(data, "entries"));
        setFilter("");
      } catch (e) {
        fail(e);
      }
    },
    [fail, setError],
  );

  const openFile = useCallback(
    async (path: string, writable?: boolean) => {
      setError("");
      setOffer("");
      say("");
      opening.current = true;
      try {
        const data = await get(`/api/file?${query({ path })}`);
        // The server says whether it can be saved: a file opened from elsewhere (a search, Mod settings) may be in logs/.
        setFile({ path, mtime: data.mtime, writable: writable !== false && data.writable !== false, text: data.text, size: data.size });
        setDraft(data.text);
      } catch (e) {
        opening.current = false;
        fail(e);
        // Too big or not text: the editor won't open it, but it can still be downloaded.
        if (e instanceof ApiError && (e.status === 413 || e.status === 415)) setOffer(path);
      }
    },
    [fail, say, setError],
  );

  // Open the folder when the tab is first shown, unless a file was opened from elsewhere in the meantime.
  useOnShow(() => {
    if (!file) void loadDir(dirRef.current, false);
  }, active);

  // Another tab (a search, Mod settings) wants a file in the raw editor.
  useBus("open-file", (detail) => {
    window.location.hash = "#files";
    void openFile(String(detail.path), detail.writable);
  });

  // A change not saved is not lost to a closed browser tab without a warning.
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const save = async () => {
    if (!file) return;
    clear();
    setSaving(true);
    try {
      const data = await api("PUT", "/api/file", { path: file.path, text: draft, mtime: file.mtime });
      const mtime = data.mtime !== undefined ? data.mtime : (await get(`/api/file?${query({ path: file.path })}`)).mtime;
      setFile({ ...file, text: draft, mtime, size: data.size });
      say("Saved. Most changes take effect after a restart.");
      setChanges((n) => n + 1);
    } catch (e) {
      fail(e);
    }
    setSaving(false);
  };

  const close = () => {
    if (dirty && file) {
      ask({
        message: `Close ${file.path} without saving? Your changes are lost.`,
        yes: "Yes, close",
        onYes: () => void loadDir(dir),
      });
      return;
    }
    void loadDir(dir);
  };

  const remove = () => {
    if (!file) return;
    const f = file;
    ask({
      message: `Delete ${f.path}? It moves to history, so it can be restored from there.`,
      yes: "Yes, delete",
      danger: true,
      onYes: async () => {
        clear();
        try {
          await post("/api/delete", { path: f.path });
          await loadDir(dir);
          say(`Deleted ${f.path}. It is in the history below.`);
          setChanges((n) => n + 1);
        } catch (e) {
          fail(e);
        }
      },
    });
  };

  const upload = async (picked: File) => {
    clear();
    if (!FILE_NAME.test(picked.name)) {
      fail("That file's name can only have letters, digits and . _ + -");
      return;
    }
    if (picked.size > MAX_UPLOAD) {
      fail("That file is over 64 MB, which is the most that can be uploaded here.");
      return;
    }
    setUploading(true);
    try {
      await api("POST", `/api/upload?${query({ path: dir, name: picked.name })}`, undefined, { raw: picked });
      await loadDir(dir);
      say(`Uploaded ${picked.name}. Most changes take effect after a restart.`);
      setChanges((n) => n + 1);
    } catch (e) {
      fail(e);
    }
    setUploading(false);
  };

  // A name typed for a new file or folder: the same letters an upload's name may have.
  const typedName = (name: string) => {
    if (!FILE_NAME.test(name) || name === "." || name === "..") {
      fail("A name can only have letters, digits and . _ + -");
      return false;
    }
    if ((entries || []).some((e) => String(e.name).toLowerCase() === name.toLowerCase())) {
      fail(`This folder already has something called ${name}.`);
      return false;
    }
    return true;
  };

  const newFile = () => {
    clear();
    ask({
      message: `Make a new, empty file in ${dir || "server"}/. Give it a name with its ending, like notes.txt.`,
      yes: "Make the file",
      field: { label: "The new file's name", placeholder: "notes.txt", max: 128 },
      onYes: async (name = "") => {
        if (!typedName(name)) return;
        const path = join(dir, name);
        try {
          // No mtime: the panel takes that as "there is no such file yet" and refuses one that is there after all.
          await api("PUT", "/api/file", { path, text: "" });
          await loadDir(dir);
          await openFile(path, true);
          setChanges((n) => n + 1);
        } catch (e) {
          fail(e);
        }
      },
    });
  };

  const newFolder = () => {
    clear();
    ask({
      message: `Make a new folder in ${dir || "server"}/.`,
      yes: "Make the folder",
      field: { label: "The new folder's name", placeholder: "Folder name", max: 128 },
      onYes: async (name = "") => {
        if (!typedName(name)) return;
        try {
          await post("/api/folder", { path: join(dir, name) });
          await loadDir(dir);
          say(`Made the folder ${name}.`);
        } catch (e) {
          fail(e);
        }
      },
    });
  };

  const rename = () => {
    if (!file) return;
    const f = file;
    clear();
    if (dirty) {
      fail("Save or close your changes first: a rename would leave them behind.");
      return;
    }
    ask({
      message: `Give ${f.path} a new name, or a path from the server folder to move it (config/old/name.toml). Nothing is replaced: a name already taken is refused.`,
      yes: "Rename",
      field: { label: "The file's new name or path", value: f.path, max: 400 },
      onYes: async (to) => {
        if (!to || to === f.path) return;
        try {
          const done = await post("/api/rename", { path: f.path, to });
          const moved: string = done.path || to;
          const where = moved.includes("/") ? moved.slice(0, moved.lastIndexOf("/")) : "";
          await loadDir(where);
          say(`${f.path} is now ${moved}.`);
          setChanges((n) => n + 1);
        } catch (e) {
          fail(e);
        }
      },
    });
  };

  const wanted = filter.trim().toLowerCase();
  const shown = (entries || []).filter((e) => !wanted || String(e.name).toLowerCase().includes(wanted));
  const parts = dir ? dir.split("/") : [];

  return (
    <>
      <PageHead title="Files">
        <p>
          The server's own folder. Worlds, libraries and databases are not shown. Every change is kept in history, so a
          save or a delete can be undone.
        </p>
      </PageHead>
      <Panels>
        {file ? (
          <Panel wide title={<span className="font-mono wrap-anywhere">{file.path}</span>}>
            <Messages of={m} />
            {offer && (
              <p>
                <a className="link" href={downloadUrl(offer)}>
                  Download it
                </a>
              </p>
            )}
            {confirm}
            <p className="fine">
              {size(file.size)}, saved {when(file.mtime)}
              {file.writable ? "" : ". Read only."}
            </p>
            <label className="sr-only" htmlFor="file-text">
              File contents
            </label>
            <Textarea
              id="file-text"
              className="h-[60dvh] min-h-56 font-mono text-[0.8125rem] whitespace-pre"
              wrap="off"
              value={draft}
              readOnly={!file.writable}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === "s" && file.writable) {
                  e.preventDefault();
                  void save();
                }
              }}
            />
            <Actions>
              {file.writable && (
                <Button kind="primary" disabled={saving} onClick={() => void save()}>
                  Save
                </Button>
              )}
              <Button onClick={close}>Close</Button>
              <a className="btn" href={downloadUrl(file.path)} download>
                Download
              </a>
              {file.writable && <Button onClick={rename}>Rename or move</Button>}
              {file.writable && (
                <Button kind="danger" onClick={remove}>
                  Delete
                </Button>
              )}
            </Actions>
          </Panel>
        ) : (
          <Panel wide title="Server folder" meta={entries ? entries.length : undefined}>
            <Messages of={m} />
            {offer && (
              <p>
                <a className="link" href={downloadUrl(offer)}>
                  Download it
                </a>
              </p>
            )}
            {confirm}
            <nav className="flex flex-wrap items-center gap-x-1 font-mono text-sage" aria-label="Folder">
              <Button kind="link" onClick={() => void loadDir("")}>
                server
              </Button>
              {parts.map((part, i) => {
                const target = parts.slice(0, i + 1).join("/");
                return (
                  <span key={target} className="flex items-center gap-x-1">
                    /
                    <Button kind="link" onClick={() => void loadDir(target)}>
                      {part}
                    </Button>
                  </span>
                );
              })}
            </nav>
            <Input
              type="search"
              maxLength={100}
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Find in this folder"
              aria-label="Show only names with this text"
            />
            <Rows label="Files in this folder">
              {entries && entries.length === 0 && <Empty>Nothing in this folder.</Empty>}
              {entries && entries.length > 0 && shown.length === 0 && <Empty>No name here has that text.</Empty>}
              {shown.map((entry) => {
                const full = join(dir, entry.name);
                const meta = [entry.dir ? "" : size(entry.size), when(entry.mtime), entry.writable ? "" : "read only"]
                  .filter(Boolean)
                  .join(", ");
                return (
                  <Row
                    key={entry.name}
                    title={
                      entry.dir ? (
                        <Button kind="link" className="font-mono wrap-anywhere text-left" onClick={() => void loadDir(full)}>{`${entry.name}/`}</Button>
                      ) : (
                        <Button kind="link" className="font-mono wrap-anywhere text-left" onClick={() => void openFile(full, entry.writable)}>
                          {entry.name}
                        </Button>
                      )
                    }
                    about={meta}
                  />
                );
              })}
            </Rows>
            {writableDir && (
              <Actions>
                <Button disabled={uploading} onClick={() => picker.current?.click()}>
                  Upload a file here
                </Button>
                <Button onClick={newFile}>New file</Button>
                <Button onClick={newFolder}>New folder</Button>
                <input
                  ref={picker}
                  type="file"
                  hidden
                  onChange={(e) => {
                    const picked = e.target.files?.[0];
                    e.target.value = "";
                    if (picked) void upload(picked);
                  }}
                />
              </Actions>
            )}
          </Panel>
        )}
        <Search />
        <Panel wide>
          <History active={active} refresh={changes} ask={ask} onError={fail} onNote={say} />
        </Panel>
      </Panels>
    </>
  );
}
