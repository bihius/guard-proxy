-- benign-mix.lua — wrk workloads for Albedo and WordPress.
--
-- LOAD_TARGET=wordpress selects installed WordPress endpoints; default Albedo
-- workload stays unchanged. Both paths of each comparison use the same mix.
local target = os.getenv("LOAD_TARGET") or "albedo"
local vhost = os.getenv("LOAD_VHOST") or (target == "wordpress" and "wp.local" or "ftw.local")
local eval_run = os.getenv("EVAL_RUN_ID") or "manual"
local eval_scenario = os.getenv("EVAL_SCENARIO") or "load"
local eval_case = os.getenv("EVAL_CASE") or "wrk"

local requests = {
  { method = "GET",  path = "/" },
  { method = "GET",  path = "/index.html" },
  { method = "GET",  path = "/static/css/main.css" },
  { method = "GET",  path = "/static/js/app.js" },
  { method = "GET",  path = "/search?q=laptop+15+inch&page=2" },
  { method = "GET",  path = "/products?category=books&sort=price&order=asc" },
  { method = "GET",  path = "/blog/2026/10/how-to-configure-a-reverse-proxy" },
  { method = "GET",  path = "/api/v1/products/42" },
  { method = "POST", path = "/login",
    content_type = "application/x-www-form-urlencoded",
    body = "username=jan.kowalski&password=Correct-Horse-7&remember=1" },
  { method = "POST", path = "/api/v1/cart",
    content_type = "application/json",
    body = '{"product_id":42,"quantity":2,"note":"gift wrap please"}' },
}
if target == "wordpress" then
  requests = {
    { method = "GET", path = "/" },
    { method = "GET", path = "/?p=1" },
    { method = "GET", path = "/?s=wordpress+tutorial" },
    { method = "GET", path = "/wp-includes/css/dist/block-library/style.min.css" },
    { method = "GET", path = "/wp-includes/js/jquery/jquery.min.js" },
    { method = "GET", path = "/wp-json/" },
    { method = "GET", path = "/wp-json/wp/v2/posts/" },
    { method = "GET", path = "/wp-login.php" },
    { method = "POST", path = "/wp-login.php",
      content_type = "application/x-www-form-urlencoded",
      body = "log=wrk-eval-nonexistent&pwd=not-a-valid-password&wp-submit=Log+In" },
  }
end

local idx = 0

function request()
  idx = idx + 1
  local r = requests[(idx % #requests) + 1]
  local hdrs = {
    ["Host"]               = vhost,
    ["User-Agent"]         = "Mozilla/5.0 (eval-lab/1.0)",
    ["Accept"]             = "text/html,application/json;q=0.9,*/*;q=0.8",
    ["Connection"]         = "keep-alive",
    ["X-GP-Eval-Run"]      = eval_run,
    ["X-GP-Eval-Scenario"] = eval_scenario,
    ["X-GP-Eval-Case"]     = eval_case,
  }
  if r.body then
    hdrs["Content-Type"] = r.content_type
    return wrk.format(r.method, r.path, hdrs, r.body)
  end
  return wrk.format(r.method, r.path, hdrs, nil)
end

function done(summary, latency, requests_per_sec)
  -- Machine-readable summary line parsed by run-load.sh.
  io.write(string.format(
    "WRK_SUMMARY requests=%d duration_us=%d rps=%.2f "..
    "lat_p50_us=%d lat_p95_us=%d lat_p99_us=%d errors=%d\n",
    summary.requests,
    summary.duration,
    summary.requests / (summary.duration / 1e6),
    latency:percentile(50),
    latency:percentile(95),
    latency:percentile(99),
    summary.errors.connect + summary.errors.read + summary.errors.write +
      summary.errors.status + summary.errors.timeout
  ))
end
