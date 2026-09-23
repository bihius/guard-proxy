-- benign-mix.lua — wrk Lua script for realistic benign load.
--
-- Cycles through a mix of legitimate-looking HTTP requests against a
-- target vhost. Used to measure baseline latency / RPS (no WAF)
-- and WAF-in-path latency / RPS (through HAProxy+Coraza).
--
-- Usage:
--   wrk -t2 -c20 -d30s -s benchmarks/lab/scenarios/load/benign-mix.lua \
--       --latency http://<host>:<port>/
--
-- The Host: header is injected per-request so HAProxy routes to the
-- correct vhost. Override VHOST env var or edit the list below.

local vhost = os.getenv("LOAD_VHOST") or "juice.local"
local eval_run = os.getenv("EVAL_RUN_ID") or "manual"
local eval_scenario = os.getenv("EVAL_SCENARIO") or "load"
local eval_case = os.getenv("EVAL_CASE") or "wrk"

-- Request pool: realistic paths for the target application.
-- Add/remove paths to match the target's URL surface.
local get_requests = {
  { method = "GET",  path = "/",                         body = nil },
  { method = "GET",  path = "/index.html",               body = nil },
  { method = "GET",  path = "/rest/admin/application-version", body = nil },
  { method = "GET",  path = "/api/v1/status",            body = nil },
  { method = "GET",  path = "/search?q=apple",           body = nil },
  { method = "GET",  path = "/search?q=login",           body = nil },
  { method = "GET",  path = "/robots.txt",               body = nil },
  { method = "GET",  path = "/favicon.ico",              body = nil },
}

-- juice-shop hashes login passwords with bcryptjs, a pure-JS *synchronous*
-- implementation that blocks Node's single event loop thread for the
-- duration of the hash. Cycling it in at the same rate as the cheap GETs
-- (1 in 9) serialises concurrent connections behind it and collapses the
-- direct (no-WAF) baseline under socket errors instead of measuring it.
-- Sending it rarely keeps it in the mix (WAF rule coverage for the login
-- path) without turning the benign load test into a bcrypt stress test.
local login_request = {
  method = "POST", path = "/api/v1/user/login",
  body = '{"email":"user@example.com","password":"password123"}',
}
local LOGIN_EVERY_N = 20

local idx = 0

function request()
  idx = idx + 1
  local r
  if idx % LOGIN_EVERY_N == 0 then
    r = login_request
  else
    r = get_requests[(idx % #get_requests) + 1]
  end
  local hdrs = {
    ["Host"]         = vhost,
    ["User-Agent"]   = "Mozilla/5.0 (eval-lab/1.0)",
    ["Accept"]       = "application/json, text/html, */*",
    ["Connection"]   = "keep-alive",
    ["X-GP-Eval-Run"] = eval_run,
    ["X-GP-Eval-Scenario"] = eval_scenario,
    ["X-GP-Eval-Case"] = eval_case,
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
