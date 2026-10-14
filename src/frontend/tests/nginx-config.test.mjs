import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const nginxConf = readFileSync(resolve(process.cwd(), "nginx.conf"), "utf8");
const dockerfile = readFileSync(resolve(process.cwd(), "Dockerfile"), "utf8");

function cspHashOfInlineScript(html) {
  const match = html.match(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/);
  assert.ok(match, "index.html should keep its inline theme script");
  return `sha256-${createHash("sha256").update(match[1]).digest("base64")}`;
}

test("the image builds the SPA and serves it as static files", () => {
  assert.match(dockerfile, /RUN pnpm build/);
  assert.match(dockerfile, /nginxinc\/nginx-unprivileged/);
  assert.doesNotMatch(dockerfile, /pnpm dev/);
  assert.doesNotMatch(dockerfile, /EXPOSE 5173/);
});

test("nginx proxies the API on the same origin and appends the client address", () => {
  assert.match(nginxConf, /location \/api\/v1\//);
  assert.match(nginxConf, /rewrite \^\/api\/v1\/\(\.\*\)\$ \/\$1 break;/);
  assert.match(nginxConf, /proxy_pass \$backend;/);
  // The backend rate-limits logins on the right-most X-Forwarded-For entry.
  assert.match(
    nginxConf,
    /proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;/,
  );
});

test("nginx serves the SPA routes and long-caches hashed assets", () => {
  assert.match(nginxConf, /try_files \$uri \/index\.html;/);
  assert.match(nginxConf, /location \/assets\//);
  assert.match(nginxConf, /expires 1y;/);
});

test("nginx sends security headers, with a CSP that matches the inline script", () => {
  assert.match(nginxConf, /add_header Content-Security-Policy "/);
  assert.match(nginxConf, /add_header X-Content-Type-Options "nosniff" always;/);
  assert.match(nginxConf, /add_header X-Frame-Options "DENY" always;/);
  assert.match(nginxConf, /frame-ancestors 'none'/);
  assert.match(nginxConf, /object-src 'none'/);

  const inlineScript = readFileSync(resolve(process.cwd(), "index.html"), "utf8");
  const hash = cspHashOfInlineScript(inlineScript);
  assert.ok(
    nginxConf.includes(hash),
    `Content-Security-Policy must allow the inline theme script (${hash})`,
  );
});
