import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const globalsCss = readFileSync(
  resolve(process.cwd(), "src", "styles", "globals.css"),
  "utf8",
);

test("Dark Reader fallback strips layered background effects", () => {
  assert.match(globalsCss, /html\[data-darkreader-mode\] \.bg-app \{/);
  assert.match(globalsCss, /html\[data-darkreader-mode\] \.card-gradient \{/);
  assert.match(globalsCss, /html\[data-darkreader-mode\] \.placeholder-card \{/);
  assert.match(globalsCss, /background-image: none;/);
});

test("Dark Reader fallback disables blur and glow-heavy shadows", () => {
  assert.match(globalsCss, /html\[data-darkreader-mode\] \.nav-surface \{/);
  assert.match(
    globalsCss,
    /html\[data-darkreader-mode\] \.backdrop-blur-sm,\s*html\[data-darkreader-mode\] \.backdrop-blur-xl \{/,
  );
  assert.match(
    globalsCss,
    /html\[data-darkreader-mode\] \.shadow-card,\s*html\[data-darkreader-mode\] \.shadow-card-lg,\s*html\[data-darkreader-mode\] \.btn-primary:active,\s*html\[data-darkreader-mode\] \.input-field:focus \{/,
  );
});

test("Dark Reader fallback restores contrast for active nav items and accent badges", () => {
  assert.match(globalsCss, /html\[data-darkreader-mode\] \.nav-link-active \{/);
  assert.match(globalsCss, /html\[data-darkreader-mode\] \.badge-accent \{/);
  assert.match(globalsCss, /background-color: var\(--color-accent\);/);
  assert.match(globalsCss, /color: var\(--color-accent-fg\);/);
});
