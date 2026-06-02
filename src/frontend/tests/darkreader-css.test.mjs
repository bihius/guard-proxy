import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const globalsCss = readFileSync(
  resolve(process.cwd(), "src", "styles", "globals.css"),
  "utf8",
);

test("Dark Reader fallback strips app background effects", () => {
  assert.match(globalsCss, /html\[data-darkreader-mode\] \.bg-app \{/);
  assert.match(globalsCss, /background-image: none;/);
});

test("Dark Reader fallback disables navigation blur", () => {
  assert.match(globalsCss, /html\[data-darkreader-mode\] \.nav-surface \{/);
  assert.match(
    globalsCss,
    /html\[data-darkreader-mode\] \.backdrop-blur-sm,\s*html\[data-darkreader-mode\] \.backdrop-blur-xl \{/,
  );
});

test("Dark Reader fallback restores contrast for active nav items", () => {
  assert.match(globalsCss, /html\[data-darkreader-mode\] \.nav-link-active \{/);
  assert.match(globalsCss, /background-color: var\(--color-accent\);/);
  assert.match(globalsCss, /color: var\(--color-accent-fg\);/);
});
