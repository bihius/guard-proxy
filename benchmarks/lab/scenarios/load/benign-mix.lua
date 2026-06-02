-- benign-mix.lua — wrk Lua script for realistic benign load.
--
-- Cycles through a mix of legitimate-looking HTTP requests against a
-- target vhost. Used to measure baseline latency / RPS (no WAF)
-- and WAF-in-path latency / RPS (through HAProxy+Coraza).
--
-- Usage:
--   wrk -t4 -c50 -d60s -s benchmarks/lab/scenarios/load/benign-mix.lua \
--       --latency http://<host>:<port>/
--
-- The Host: header is injected per-request so HAProxy routes to the
-- correct vhost. Override VHOST env var or edit the list below.

local vhost = os.getenv("LOAD_VHOST") or "juice.local"

-- Request pool: realistic paths for the target application.
-- Add/remove paths to match the target's URL surface.
local requests = {
  { method = "GET",  path = "/",                         body = nil },
  { method = "GET",  path = "/index.html",               body = nil },
  { method = "GET",  path = "/rest/admin/application-version", body = nil },
  { method = "GET",  path = "/api/v1/status",            body = nil },
  { method = "GET",  path = "/search?q=apple",           body = nil },
  { method = "GET",  path = "/search?q=login",           body = nil },
  { method = "GET",  path = "/robots.txt",               body = nil },
  { method = "GET",  path = "/favicon.ico",              body = nil },
  { method = "POST", path = "/api/v1/user/login",
    body = '{"email":"user@example.com","password":"password123"}' },
}

local idx = 0

function request()
  idx = (idx % #requests) + 1
  local r = requests[idx]
  local hdrs = {
    ["Host"]         = vhost,
    ["User-Agent"]   = "Mozilla/5.0 (eval-lab/1.0)",
    ["Accept"]       = "application/json, text/html, */*",
    ["Connection"]   = "keep-alive",
  }
  if r.body then
    hdrs["Content-Type"]   = "application/json"
    hdrs["Content-Length"] = tostring(#r.body)
    return wrk.format(r.method, r.path, hdrs, r.body)
  end
  return wrk.format(r.method, r.path, hdrs, nil)
end

function done(summary, latency, requests_per_sec)
  -- Print a machine-readable summary line for collect-metrics.sh to parse.
  io.write(string.format(
    "WRK_SUMMARY requests=%d duration_us=%d rps=%.2f "..
    "lat_p50_us=%d lat_p95_us=%d lat_p99_us=%d errors=%d\n",
    summary.requests,
    summary.duration,
    summary.requests / (summary.duration / 1e6),
    latency:percentile(50),
    latency:percentile(95),
    latency:percentile(99),
    summary.errors.connect + summary.errors.read + summary.errors.write + summary.errors.status
  ))
end
