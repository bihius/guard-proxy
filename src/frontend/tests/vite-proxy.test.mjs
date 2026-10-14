import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const viteConfig = readFileSync(
  resolve(process.cwd(), "vite.config.ts"),
  "utf8",
);

test("dev server proxy forwards the client address to the backend", () => {
  // The backend rate-limits logins on the right-most X-Forwarded-For entry, so
  // a proxy that forwards requests without adding one (or forwards the client's
  // own header untouched) leaves the limiter keyed on what the caller sent.
  assert.match(viteConfig, /xfwd:\s*true/);
});

test("dev server proxy keeps stripping the api prefix", () => {
  assert.match(viteConfig, /rewrite:.*\^\\\/api\\\/v1/);
});
