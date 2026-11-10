// Run with `bun test`. Where the checksum list for the pack files is (SHA256SUMS.txt, tools/checksums.py).
import assert from "node:assert/strict";
import { test } from "node:test";
import { checksumsBeside, checksumsUrl, config } from "./config";

test("the checksum list is beside the first file the site serves itself", () => {
  assert.equal(checksumsBeside(["pack/a.mrpack", "pack/b.zip"]), "/pack/SHA256SUMS.txt");
  assert.equal(checksumsBeside(["https://modrinth.com/modpack/monkeysmp", "/pack/b.zip?v=2"]), "/pack/SHA256SUMS.txt");
  assert.equal(checksumsBeside(["a.mrpack"]), "/SHA256SUMS.txt");
});

test("no list when every download is a link elsewhere, or not set", () => {
  assert.equal(checksumsBeside(["https://modrinth.com/modpack/monkeysmp", "//cdn.example/b.zip"]), "");
  assert.equal(checksumsBeside(["", ""]), "");
});

test("the front page's link follows config.json", () => {
  assert.equal(checksumsUrl, checksumsBeside([config.MODPACK_URL, config.INSTALLER_URL]));
});
